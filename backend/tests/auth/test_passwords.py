from compliance.auth.passwords import hash_password, verify_password


class TestPasswordHashing:
    def test_hashed_password_verifies_original_password(self) -> None:
        hashed_password = hash_password("correct-password")

        assert verify_password("correct-password", hashed_password) is True

    def test_hashed_password_rejects_different_password(self) -> None:
        hashed_password = hash_password("correct-password")

        assert verify_password("wrong-password", hashed_password) is False
