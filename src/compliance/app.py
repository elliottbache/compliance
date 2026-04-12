from compliance.db.query_history import get_site_history


def main():
    print("app mainer")
    pass

if __name__ == "__main__":
    print(f"site 1: {get_site_history(1)}")
    print(f"site 71: {get_site_history(71)}")
    print(f"site 72: {get_site_history(72)}")
