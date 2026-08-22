"""Establishment tag enum."""

from enum import StrEnum


class EstablishmentTag(StrEnum):
    cafe = "Cafe"
    qsr = "QSR"
    restaurant = "Restaurant"
    hotel = "Hotel"
    other = "Other"
