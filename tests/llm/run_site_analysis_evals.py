import json
import logging
from collections.abc import Generator
from pathlib import Path
from typing import Any

import spacy
from pydantic import BaseModel, ValidationError

from compliance._helpers import validate_llm_references
from compliance.llm.anthropic_api import summarize_previous_visits
from compliance.llm.schemas import (
    ExpectedResults,
    HumanReviewItem,
    MissingInfoItem,
    RecurringIssueItem,
    ResultChecks,
    SiteAnalysis,
    SuggestionItem,
)
from compliance.schemas import Site

_DEFAULT_INPUT_FILE = Path("input_site_history.json")
_DEFAULT_EXPECTED_FILE = Path("expected.json")
_DEFAULT_CASES_DIRECTORY = Path("tests/llm/evals/site_history_cases")
_DEFAULT_RESULTS_FILE = _DEFAULT_CASES_DIRECTORY / "eval_results.json"
_DEFAULT_AI_MODEL = (
    "claude-haiku-4-5-20251001"  # options: claude-opus-4-6, claude-haiku-4-5-20251001
)
_DEFAULT_MINIMUM_EVIDENCE = {
    "recurring_issues": 2,
    "missing_information": 1,
    "needs_human_review": 1,
}
logger = logging.getLogger(__name__)
# Create a blank English model and add sentencizer
_nlp = spacy.blank("en")
_nlp.add_pipe("sentencizer")


def run_evals(
    evals_path: Path = _DEFAULT_CASES_DIRECTORY, *, case_name: str | None = None
) -> None:
    """Run evaluation cases and collect model parsing and comparison results.

    Iterates through evaluation case directories, loads the input and expected
    files for each case, runs the site history summarization flow, and stores
    parse status, retry status, model output, and deterministic validation checks.

    Args:
        evals_path: Directory containing evaluation case subdirectories.
        case_name: Optional name of a specific case to run. If provided,
            only this case is evaluated; otherwise, all cases in
            evals_path are processed.

    Returns:
        None
    """
    # loop through eval folders
    eval_results = dict()
    input_filename = _DEFAULT_INPUT_FILE
    expected_filename = _DEFAULT_EXPECTED_FILE

    # if given a case name, only use that case name.  Otherwise, walk through directory.
    cases = (
        [case_name]
        if case_name
        else _eval_case_generator(
            evals_path,
            input_filename=input_filename,
            expected_filename=expected_filename,
        )
    )
    for case in cases:
        case_path = evals_path / case
        # load each eval case
        with open(case_path / input_filename) as f:
            site_history = Site.model_validate(json.load(f))
        with open(case_path / expected_filename) as f:
            expected_results = ExpectedResults.model_validate(json.load(f))

        # run your current prompt + model call
        eval_results[case] = dict()
        try:
            is_retry, prompt_version, response = summarize_previous_visits(
                site_history, ai_model=_DEFAULT_AI_MODEL, case_info=case
            )

            # record the prompt version
            eval_results[case]["prompt_version"] = prompt_version

            # record whether structured parse succeeded
            eval_results[case]["parse_succeeded"] = True

            # record whether the query had to be retried
            eval_results[case]["is_retry"] = is_retry

            # record the parsed result
            eval_results[case]["model_results"] = response

            # record the expected results
            eval_results[case]["expected_results"] = expected_results

            # run a few deterministic checks
            eval_results[case]["response_checks"] = _compare_results_to_expected(
                response, expected_results, site_history
            )

        except ValidationError:
            # record whether structured parse succeeded
            eval_results[case]["parse_succeeded"] = False

        # record LLM model name
        eval_results[case]["model_name"] = _DEFAULT_AI_MODEL

    _write_eval_results(eval_results, _DEFAULT_RESULTS_FILE)


def _eval_case_generator(
    evals_path: Path, *, input_filename: Path, expected_filename: Path
) -> Generator[str, None, None]:
    """Yield directory name for valid evaluation case directories.

    Checks each immediate subdirectory of `evals_path` and yields a directory
    name when both the input file and expected file are present.

    Args:
        evals_path: Directory containing evaluation case subdirectories.
        input_filename: Name of the input file expected in each case directory.
        expected_filename: Name of the expected output file expected in each case
            directory.

    Yields:
        tuple[Path, None, None]: Name the valid evaluation case directory.
    """
    for path in evals_path.iterdir():
        if (
            path.is_dir()
            and (path / input_filename).exists()
            and (path / expected_filename).exists()
        ):
            yield path.parts[-1]


def _compare_results_to_expected(
    resp: SiteAnalysis, exp: ExpectedResults, site_history: Site
) -> ResultChecks:
    """Compare a model response against the expected summary checks.

    Evaluates whether the response matches expected identifiers, counts, phrase
    coverage, required rule mentions, required evidence, and the presence of
    forbidden content.

    Args:
        resp: Parsed model response to validate.
        exp: Expected values and phrases used to evaluate the response.

    Returns:
        ResultChecks: Validation results for each comparison criterion.
    """
    checks = dict()
    checks["is_site_id_correct"] = resp.site_id == exp.site_id
    checks["is_n_inspections_correct"] = resp.inspection_count == exp.inspection_count
    checks["is_max_summary_sentences"] = (
        _count_sentences(resp.executive_summary) <= exp.max_summary_sentences
    )

    checks["is_summary_phrases"] = all(
        ex.lower() in resp.executive_summary.lower() for ex in exp.summary_phrases
    )

    for attr_name in ["recurring_issues", "missing_information", "needs_human_review"]:
        checks["is_" + attr_name] = _is_strings_in_object_list(
            resp=resp, exp=getattr(exp, attr_name, []), attr_name=attr_name
        )

    response_texts = _create_one_big_string(resp)
    checks["is_rule_mentions"] = all(
        rule_mention.lower() in response_texts.lower()
        for rule_mention in exp.rule_mentions
    )

    checks["is_valid_references"] = _is_valid_references(resp, site_history)

    checks["is_evidence_references"] = _validate_evidence_lengths(resp)

    checks["is_forbidden_phrases"] = any(
        forbidden_phrase.lower() in response_texts.lower()
        for forbidden_phrase in exp.forbidden_phrases
    )
    checks["is_forbidden_summary_terms"] = any(
        forbidden_summary_term.lower() in resp.executive_summary.lower()
        for forbidden_summary_term in exp.forbidden_summary_terms
    )

    return ResultChecks.model_validate(checks)


def _count_sentences(text: str) -> int:
    return len(list(_nlp(text).sents))


def _is_strings_in_object_list(
    *, resp: SiteAnalysis, exp: list[str], attr_name: str
) -> bool:
    """Check whether each expected string appears somewhere in the SiteAnalysis
    attribute."""
    full_text = _create_one_big_string(getattr(resp, attr_name))
    return all(ex.lower() in full_text.lower() for ex in exp)


def _create_one_big_string(obj: Any) -> str:
    """Recursively finds all strings in an object and joins them."""
    found_strings = []

    def _walk(current):
        if isinstance(current, str):
            found_strings.append(current)
        elif isinstance(current, (list | tuple)):
            for item in current:
                _walk(item)
        elif isinstance(current, dict):
            for value in current.values():
                _walk(value)
        elif isinstance(current, BaseModel):
            # Recursively walk the dumped dictionary
            _walk(current.model_dump())
        elif hasattr(current, "__dict__"):
            _walk(vars(current))

    _walk(obj)

    return " ".join(found_strings)


def _is_valid_references(resp: SiteAnalysis, site_history: Site) -> bool:
    try:
        validate_llm_references(resp, site_history)
        return True
    except ValueError:
        return False
    except Exception:
        raise


def _validate_evidence_lengths(resp: SiteAnalysis, *, minimum_lengths=None) -> bool:
    if minimum_lengths is None:
        minimum_lengths = _DEFAULT_MINIMUM_EVIDENCE
    target_fields = [
        "recurring_issues",
        "missing_information",
        "needs_human_review",
    ]
    for field_name in target_fields:
        item_objects = getattr(resp, field_name)
        for item_object in item_objects:
            if len(item_object.evidence) < minimum_lengths[field_name]:
                return False

    return True


def _write_eval_results(eval_results: dict[str, Any], outfile: Path) -> None:
    """Write pertinent results to file."""
    to_write = dict()
    failed_cases = list()
    for case_name in eval_results:
        to_write[case_name] = dict()
        to_write[case_name]["model_name"] = eval_results[case_name]["model_name"]
        to_write[case_name]["parse_success"] = eval_results[case_name][
            "parse_succeeded"
        ]
        if not to_write[case_name]["parse_success"]:
            to_write[case_name]["failures"] = ["parse_failed"]
            continue
        to_write[case_name]["prompt_version"] = eval_results[case_name][
            "prompt_version"
        ]
        to_write[case_name]["is_retry"] = eval_results[case_name]["is_retry"]
        to_write[case_name]["output_summary"] = eval_results[case_name][
            "model_results"
        ].executive_summary
        to_write[case_name]["failures"] = _find_failed_checks(
            eval_results[case_name]["response_checks"]
        )
        if to_write[case_name]["failures"]:
            to_write[case_name]["model_results"] = eval_results[case_name][
                "model_results"
            ].model_dump(mode="json")
            to_write[case_name]["expected_results"] = eval_results[case_name][
                "expected_results"
            ].model_dump(mode="json")
            failed_cases.append(case_name)

        checks = [field_name for field_name in ResultChecks.model_fields]
        logger.info(
            f"Case name: {case_name}, failed checks: {to_write[case_name]["failures"]},"
            f" pass/fail checks: {checks},"
            f" summary_output: {to_write[case_name]["output_summary"]}"
        )

    to_write["failed_cases"] = failed_cases

    # write a results file
    with open(outfile, mode="w") as f:
        json.dump(to_write, f, indent=4)


def _find_failed_checks(checks: ResultChecks) -> list[str]:
    """Return the names of failed summary checks.

    Treats standard validation fields as failed when their value is `False` and
    forbidden-content fields as failed when their value is `True`.

    Args:
        checks: Summary check results to evaluate.

    Returns:
        list[str]: Names of fields that represent failed checks.
    """
    normal_checks = {
        "is_site_id_correct",
        "is_n_inspections_correct",
        "is_max_summary_sentences",
        "is_summary_phrases",
        "is_recurring_issues",
        "is_missing_information",
        "is_needs_human_review",
        "is_rule_mentions",
    }

    forbidden_checks = {
        "is_forbidden_phrases",
        "is_forbidden_summary_terms",
    }

    return [
        field_name
        for field_name in ResultChecks.model_fields
        if (field_name in normal_checks and not getattr(checks, field_name))
        or (field_name in forbidden_checks and getattr(checks, field_name))
    ]


if __name__ == "__main__":
    from compliance.logging_utils import configure_logging

    configure_logging(level="DEBUG", node="debug", is_tutorial=False)
    # run_evals(case_name="no_findings")
    run_evals()
