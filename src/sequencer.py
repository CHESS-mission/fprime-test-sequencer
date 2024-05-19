import re
import time

from fprime_gds.common.data_types.event_data import EventData
from fprime_gds.common.testing_fw.api import IntegrationTestAPI
from src.parser.parser import ExpectEventInstruction, Sequence


def run_sequence(seq: Sequence, api: IntegrationTestAPI):
    starting_time_s = time.time()
    def elapsed_time_s():
        return time.time() - starting_time_s

    commands = seq.get_ordered_commands()
    max_send_time_digits = len(str(commands[-1].send_time_ms))

    for command in commands:
        # Sleep until next command
        time.sleep(max(0.001 * command.send_time_ms - elapsed_time_s(), 0))
        # Send command
        print(f"[{round(1000 * elapsed_time_s()):{max_send_time_digits}} ms]: Sending command {command.command} {' '.join(command.args)}")
        api.send_command(command.command, command.args)


def find_event(expected_event: ExpectEventInstruction, events: list[EventData], starting_time: float) -> EventData | None:
    for event in events:
        match_ = True
        # print()
        # print(f"{0.001 * expected_event.start_time_ms} <= {event.get_time().get_float() - starting_time} <= {event_end_time}")
        match_ &= 0.001 * expected_event.start_time_ms <= event.get_time().get_float() - starting_time <= 0.001 * expected_event.end_time_ms
        # print(f"{expected_event.event} == {event.get_severity()} or {expected_event.event} == {event.template.get_full_name()}")
        match_ &= expected_event.event == event.get_severity() or expected_event.event == event.template.get_full_name()
        if expected_event.expected_value != None:
            if expected_event.is_regex:
                # print(f"{re.search(expected_event.expected_value, event.get_display_text())} != None")
                match_ &= re.search(expected_event.expected_value, event.get_display_text()) != None
            else:
                # print(f"{expected_event.expected_value} == {event.get_display_text()}")
                match_ &= expected_event.expected_value == event.get_display_text()
        if match_:
            return event
    return None


def validate_sequence(seq: Sequence, starting_time: float, api: IntegrationTestAPI):
    ok = "\033[92m[OK]\033[0m"
    fail = "\033[91m[FAIL]\033[0m"

    for expected_event in seq.event_instrs:
        matching_event = find_event(expected_event, api.get_event_test_history().retrieve(), starting_time)
        if matching_event != None:
            timing = f"[{round(1000 * (matching_event.get_time().get_float() - starting_time))} ms]"
            severity = matching_event.get_severity()
            name = matching_event.template.get_full_name()
            value = "" if matching_event.get_display_text() == "" else f"\"{matching_event.get_display_text()}\""
            match_ = f"{timing} {severity} {name} {value}"
        else:
            match_ = "None"
        timing = f"[{expected_event.start_time_ms}:{expected_event.end_time_ms}]"
        event = f"EXPECT{'' if expected_event.is_expected else ' NO'} EVENT {expected_event.event}"
        value = "" if expected_event.expected_value == None else f" {'re' if expected_event.is_regex else ''}\"{expected_event.expected_value}\""
        result = f"{ok if (matching_event != None) == expected_event.is_expected else fail}"
        print(f"{timing} {event}{value}: {result} ~> {match_}")
