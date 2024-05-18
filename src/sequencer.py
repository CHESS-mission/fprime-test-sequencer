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


def find_event(expected_event: ExpectEventInstruction, events: list[EventData], starting_time: float, end_time_ms: float):
    for event in events:
        match_ = True
        event_end_time = 0.001 * expected_event.end_time_ms if expected_event.end_time_ms != -1 else end_time_ms
        print()
        print(f"{0.001 * expected_event.start_time_ms} <= {event.get_time().get_float() - starting_time} <= {event_end_time}")
        match_ &= 0.001 * expected_event.start_time_ms <= event.get_time().get_float() - starting_time <= event_end_time
        print(f"{expected_event.event} == {event.get_severity()} or {expected_event.event} == {event.template.get_full_name()}")
        match_ &= expected_event.event == event.get_severity() or expected_event.event == event.template.get_full_name()
        if expected_event.expected_value != None:
            if expected_event.is_regex:
                print(f"{re.search(expected_event.expected_value, event.get_display_text())} != None")
                match_ &= re.search(expected_event.expected_value, event.get_display_text()) != None
            else:
                print(f"{expected_event.expected_value} == {event.get_display_text()}")
                match_ &= expected_event.expected_value == event.get_display_text()
        if match_:
            return True
    return False


def validate_sequence(seq: Sequence, starting_time: float, api: IntegrationTestAPI):
    for expected_event in seq.event_instrs:
        print(f"{expected_event.event}: {find_event(expected_event, api.get_event_test_history().retrieve(), starting_time, 0.001 * seq.get_duration())}")
        print("-------------------------")
