from pwdlib import PasswordHash

"""fake_users_db = {
    "johndoe": {
        "username": "johndoe",
        "full_name": "John Doe",
        "email": "johndoe@example.com",
        "hashed_password": "$argon2id$v=19$m=65536,t=3,p=4$wagCPXjifgvUFBzq4hqe3w$CYaIb8sB+wtD+Vu/P4uod1+Qof8h+1g7bbDlBID48Rc",
        "disabled": False,
    }
}"""

password_hash = PasswordHash.recommended()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return whether a plaintext password matches a stored password hash."""
    return password_hash.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    """Hash a plaintext password using the configured password hasher."""
    return password_hash.hash(password)


"""def authenticate_user(fake_db, username: str, password: str, stored_hash: str):
    user = get_user(fake_db, username)
    if not user:
        verify_password(password, stored_hash)
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user"""

if __name__ == "__main__":

    DUMMY_HASH = hash_password("dummypassword")

    # print(authenticate_user(fake_db, "johndoe", password, DUMMY_HASH))
