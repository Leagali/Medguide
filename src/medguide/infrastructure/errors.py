class PipelineError(Exception):
    def __init__(self, code: str, *, transient: bool = False, retry_after: float = 0) -> None:
        super().__init__(code)
        self.code = code
        self.transient = transient
        self.retry_after = retry_after


class LeaseLost(PipelineError):
    def __init__(self) -> None:
        super().__init__("LEASE_LOST")
