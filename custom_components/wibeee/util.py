import re


def short_mac(mac_addr):
    """Returns the last 6 chars of the MAC address for showing in UI."""
    return mac_addr.replace(':', '')[-6:].upper()


def scrub_xml_text_naively(keys: list[str], xml_text: str) -> str:
    """Naively use a RegEx (facepalm) to scrub values from XML text."""
    scrubbed_text = re.sub(f'<({"|".join(keys)})>.*?</\\1>', f'<\\1>*MASKED*</\\1>', xml_text)
    return scrubbed_text


def scrub_dict_top_level(keys: list[str], values: dict) -> dict:
    """Scrubs values from """
    scrubbed_values = dict(values)
    for scrub_key in keys:
        if scrub_key in values:
            scrubbed_values.update({scrub_key: '*MASKED*'})

    return scrubbed_values
