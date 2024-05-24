from fprime_gds.common.data_types.ch_data import ChData
from fprime_gds.common.data_types.event_data import EventData


def make_green(s: str) -> str:
    return f"\033[92m{s}\033[0m"


def make_red(s: str) -> str:
    return f"\033[91m{s}\033[0m"


def time_to_relative_ms(starting_time: float):
    def time_to_ms(time: float):
        return round(1000 * (time - starting_time))
    return time_to_ms


def event_data_to_str(ed: EventData, starting_time: float=0, with_timing=True) -> str:
    severity = ed.get_severity()
    name = ed.template.get_full_name()
    value = "" if ed.get_display_text() == "" else f"\"{ed.get_display_text()}\""
    if with_timing:
        timing = f"[{time_to_relative_ms(starting_time)(ed.get_time().get_float())} ms]"
        return f"{timing} {severity} {name} {value}"
    else:
        return f"{severity} {name} {value}"


def ch_data_to_str(cd: ChData, starting_time: float=0, with_timing=True) -> str:
    name = cd.template.get_full_name()
    value = "" if cd.get_display_text() == "" else f"\"{cd.get_display_text()}\""
    if with_timing:
        timing = f"[{time_to_relative_ms(starting_time)(cd.get_time().get_float())} ms]"
        return f"{timing} {name} {value}"
    else:
        return f"{name} {value}"
