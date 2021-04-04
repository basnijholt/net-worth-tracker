import keyring


def get_password(username: str, service: str):
    pw = keyring.get_password(service, username)
    if not pw:
        raise Exception(f"python -m keyring set {service} {username}")
    return pw
