class LocatorNotFound(Exception):
    def __init__(self, locator: dict):
        super().__init__(f"could not resolve locator: {locator!r}")
        self.locator = locator
