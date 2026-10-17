class PipelineError(Exception):
    def __init__(self, code: str, *, transient: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.transient = transient


class LeaseLost(PipelineError):
    def __init__(self) -> None:
        super().__init__("LEASE_LOST")
