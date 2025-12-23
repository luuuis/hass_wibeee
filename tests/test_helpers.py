"""Shared test helpers for Wibeee tests."""
from typing import Dict, Any

from custom_components.wibeee.sensor import DeviceInfo


def build_values(info: DeviceInfo, sensor_values: Dict[str, Any]) -> Dict[str, Any]:
    """Build test values dictionary for a device."""
    return {
        'id': info.id,
        'softVersion': info.softVersion,
        'ipAddr': info.ipAddr,
        'macAddr': info.macAddr,
    } | sensor_values