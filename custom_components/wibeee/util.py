def short_mac(mac_addr):
    """Returns the last 6 chars of the MAC address for showing in UI."""
    return mac_addr.replace(':', '')[-6:].upper()
