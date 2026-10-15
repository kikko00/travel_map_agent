"""Public, credential-free errors for upstream model failures."""
class ModelTimeoutError(TimeoutError):
    pass


class ModelServiceError(RuntimeError):
    pass


class ModelOutputError(ModelServiceError):
    pass
