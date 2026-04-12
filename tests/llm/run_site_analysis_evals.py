import json
import logging
import spacy
import pickle

from pathlib import Path
from pydantic import ValidationError
from typing import Generator, Any

from anthropic_api import summarize_previous_visits
from schemas import Site, ModelSummary, SiteAnalysis, SummaryChecks

_DEFAULT_INPUT_FILE = Path("input_site_history.json")
_DEFAULT_EXPECTED_FILE = Path("expected.json")
_DEFAULT_CASES_DIRECTORY = Path("evals/site_history_cases")
_DEFAULT_RESULTS_FILE = _DEFAULT_CASES_DIRECTORY / "eval_results.json"
_DEFAULT_AI_MODEL = "claude-haiku-4-5-20251001"  # options: claude-opus-4-6, claude-haiku-4-5-20251001

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__
                           )
# Create a blank English model and add sentencizer
_nlp = spacy.blank("en")
_nlp.add_pipe("sentencizer")


def run_evals(evals_path: Path = _DEFAULT_CASES_DIRECTORY) -> None:
    """Run evaluation cases and collect model parsing and comparison results.

    Iterates through evaluation case directories, loads the input and expected
    files for each case, runs the site history summarization flow, and stores
    parse status, retry status, model output, and deterministic validation checks.

    Args:
        evals_path: Directory containing evaluation case subdirectories.

    Returns:
        None
    """
    # loop through eval folders
    eval_results = dict()
    input_filename = _DEFAULT_INPUT_FILE
    expected_filename = _DEFAULT_EXPECTED_FILE
    for case_name in _eval_case_generator(
        evals_path,
        input_filename=input_filename,
        expected_filename=expected_filename
    ):
        case_path = evals_path / case_name
        # load each eval case
        with open(case_path / input_filename) as f:
            site_history = Site.model_validate(json.load(f))
        with open(case_path / expected_filename) as f:
            expected_results = ModelSummary.model_validate(json.load(f))

        # run your current prompt + model call
        eval_results[case_name] = dict()
        try:
            is_retry, prompt_version, response = summarize_previous_visits(site_history, ai_model=_DEFAULT_AI_MODEL)

            # record the prompt version
            eval_results[case_name]["prompt_version"] = prompt_version

            # record whether structured parse succeeded
            eval_results[case_name]["parse_succeeded"] = True

            # record whether the query had to be retried
            eval_results[case_name]["is_retry"] = True if is_retry else False

            # record the parsed result
            eval_results[case_name]["model_results"] = response

            # record the expected results
            eval_results[case_name]["expected_results"] = expected_results

            # run a few deterministic checks
            eval_results[case_name]["response_checks"] = \
                _compare_results_to_expected(response, expected_results)


        except ValidationError:
            # record whether structured parse succeeded
            eval_results[case_name]["parse_succeeded"] = False

        # record LLM model name
        eval_results[case_name]["model_name"] = _DEFAULT_AI_MODEL

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
        if path.is_dir():
            if (path / input_filename).exists() and (path / expected_filename).exists():
                yield path.parts[-1]


def _compare_results_to_expected(resp: SiteAnalysis, exp: ModelSummary) -> SummaryChecks:
    """Compare a model response against the expected summary checks.

    Evaluates whether the response matches expected identifiers, counts, phrase
    coverage, required rule mentions, and the presence of forbidden content.

    Args:
        resp: Parsed model response to validate.
        exp: Expected values and phrases used to evaluate the response.

    Returns:
        SummaryChecks: Validation results for each comparison criterion.
    """
    checks = dict()
    checks["is_site_id_correct"] = resp.site_id == exp.site_id
    checks["is_n_inspections_correct"] = resp.inspection_count == exp.inspection_count
    checks["is_max_summary_sentences"] = \
        _count_sentences(resp.summary) <= exp.max_summary_sentences
    checks["is_summary_phrases"] = _is_strings_in([resp.summary], exp.summary_phrases)
    checks["is_recurring_issues"] = _is_strings_in(resp.recurring_issues, exp.recurring_issues)
    checks["is_missing_information"] = _is_strings_in(resp.missing_information, exp.missing_information)
    checks["is_needs_human_review"] = _is_strings_in(resp.needs_human_review, exp.needs_human_review)
    response_texts = (
            [resp.summary]
            + resp.recurring_issues
            + resp.missing_information
            + resp.needs_human_review
            + resp.inspection_caveats
            + resp.suggestions
    )
    checks["is_rule_mentions"] = all(
        any(rule_mention.lower() in text.lower() for text in response_texts)
        for rule_mention in exp.rule_mentions
    )
    checks["is_forbidden_phrases"] = any(
        any(forbidden_phrase.lower() in text.lower() for text in response_texts)
        for forbidden_phrase in exp.forbidden_phrases
    )
    checks["is_forbidden_summary_terms"] = any(
        forbidden_summary_term.lower() in resp.summary.lower()
        for forbidden_summary_term in exp.forbidden_summary_terms
    )

    return SummaryChecks.model_validate(checks)


def _count_sentences(text: str) -> int:
    return len(list(_nlp(text).sents))


def _is_strings_in(resp: list[str], exp: list[str]) -> bool:
    """Check whether each expected string appears in at least one response string."""
    for ex in exp:
        if not any(ex.lower() in res.lower() for res in resp):
            return False

    return True


def _write_eval_results(eval_results: dict[str, Any], outfile: Path) -> None:
    """Write pertinent results to file."""
    to_write = dict()
    for case_name in eval_results:
        to_write[case_name] = dict()
        to_write[case_name]["model_name"] = eval_results[case_name]["model_name"]
        to_write[case_name]["parse_success"] = eval_results[case_name]["parse_succeeded"]
        if not to_write[case_name]["parse_success"]:
            to_write[case_name]["failures"] = ["parse_failed"]
            continue
        to_write[case_name]["prompt_version"] = eval_results[case_name]["prompt_version"]
        to_write[case_name]["is_retry"] = eval_results[case_name]["is_retry"]
        to_write[case_name]["output_summary"] = eval_results[case_name]["model_results"].summary
        to_write[case_name]["failures"] = _find_failed_checks(eval_results[case_name]["response_checks"])
        if to_write[case_name]["failures"]:
            to_write[case_name]["model_results"] = eval_results[case_name]["model_results"]
            to_write[case_name]["expected_results"] = eval_results[case_name]["expected_results"]

        checks = [field_name for field_name in SummaryChecks.model_fields]
        logger.info(
            f"Case name: {case_name}, failed checks: {to_write[case_name]["failures"]},"
            f" pass/fail checks: {checks},"
            f" summary_output: {to_write[case_name]["output_summary"]}"
        )

    # write a results file
    with open(outfile, mode="w") as f:
        json.dump(to_write, f, indent=4)


def _find_failed_checks(checks: SummaryChecks) -> list[str]:
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
        for field_name in SummaryChecks.model_fields
        if (field_name in normal_checks and not getattr(checks, field_name))
           or (field_name in forbidden_checks and getattr(checks, field_name))
    ]


if __name__ == "__main__":
    run_evals()