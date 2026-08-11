from enum import StrEnum


class ClientMessageTarget(StrEnum):
    all = "all"
    specific = "specific"


class ClientMessageType(StrEnum):
    seasonal = "seasonal"
    action = "action"
    announcement = "announcement"
    benchmark = "benchmark"
