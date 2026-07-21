"""Composed hardware-advisor profile logic."""

from .device_profiles import DeviceProfileMixin
from .profile_ranking import ProfileRankingMixin


class ProfileMixin(ProfileRankingMixin, DeviceProfileMixin):
    """Provide device selection and saved recommendation profiles."""

