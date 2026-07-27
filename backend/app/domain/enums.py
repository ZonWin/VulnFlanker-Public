from enum import Enum


class MatchStatus(str, Enum):
    affected = "affected"
    not_affected = "not_affected"
    needs_review = "needs_review"
    verified = "verified"
    suppressed = "suppressed"


class EnvironmentType(str, Enum):
    production = "production"
    test = "test"
    office = "office"
    dmz = "dmz"


class ExposureType(str, Enum):
    public = "public"
    internal = "internal"
    isolated = "isolated"

