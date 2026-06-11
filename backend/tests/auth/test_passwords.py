from compliance.auth.authentication import _hash_password, _verify_password


class TestPasswordHashing:
    def test_hashed_password_verifies_original_password(self) -> None:
        hashed_password = _hash_password("correct-password")

        assert _verify_password("correct-password", hashed_password) is True

    def test_hashed_password_rejects_different_password(self) -> None:
        hashed_password = _hash_password("correct-password")

        assert _verify_password("wrong-password", hashed_password) is False
