from io import BytesIO

from lxml import etree


def short_mac(mac_addr):
    """Returns the last 6 chars of the MAC address for showing in UI."""
    return mac_addr.replace(':', '')[-6:].upper()


def scrub_values_xml(keys: list[str], xml_text: bytes) -> str:
    """Scrubs sensitive data from the values.xml response."""
    tree = etree.parse(BytesIO(xml_text))

    # <values><variable><id>ssid</id><value>MY_SSID</value></variable></values>
    for key in keys:
        values = tree.xpath(f"/values/variable[id/text()='{key}']/value")
        for v in values:
            v.text = '*MASKED*'

    return etree.tostring(tree)
