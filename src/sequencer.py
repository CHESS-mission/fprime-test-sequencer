import re
import time

from fprime_gds.common.data_types.ch_data import ChData
from fprime_gds.common.data_types.event_data import EventData
from fprime_gds.common.testing_fw.api import IntegrationTestAPI
from src.parser.parser import ExpectEventInstruction, ExpectTelemetryInstruction, Sequence

def make_green(s: str) -> str:
    return f"\033[92m{s}\033[0m"

def make_red(s: str) -> str:
    return f"\033[91m{s}\033[0m"

class Sequencer:
    def __init__(self, api: IntegrationTestAPI) -> None:
        self.api = api


    def run_and_validate_sequence(self, seq: Sequence) -> bool:
        header = f" [RUNNING TEST {seq.name}] "
        print(f"{header:=^80s}")

        starting_time = time.time()
        self.run_sequence(seq)

        remaining_time = max(0, starting_time + 0.001 * seq.get_duration() - time.time())
        print(f"\nWaiting {remaining_time:.2f} seconds for the sequence to finish...")
        time.sleep(remaining_time)
        print()

        success = self.validate_sequence(seq, starting_time)

        footer = f" [TEST {seq.name} {make_green('PASSED') if success else make_red('FAILED')}] "
        print(f"\n{footer:=^89s}")

        return success


    def run_sequence(self, seq: Sequence):
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
            self.api.send_command(command.command, command.args)


    def find_matching_event(self, event: ExpectEventInstruction, starting_time: float) -> EventData | None:
        for received_event in self.api.get_event_test_history().retrieve():
            match_ = True
            match_ &= 0.001 * event.start_time_ms <= received_event.get_time().get_float() - starting_time <= 0.001 * event.end_time_ms
            match_ &= event.event == received_event.get_severity() or event.event == received_event.template.get_full_name()
            if event.expected_value != None:
                if event.is_regex:
                    match_ &= re.search(event.expected_value, received_event.get_display_text()) != None
                else:
                    match_ &= event.expected_value == received_event.get_display_text()
            if match_:
                return received_event
        return None

    def find_matching_telemetry(self, telemetry: ExpectTelemetryInstruction, starting_time: float) -> ChData | None:
        for received_telemetry in self.api.get_telemetry_test_history().retrieve():
            match_ = True
            match_ &= 0.001 * telemetry.start_time_ms <= received_telemetry.get_time().get_float() - starting_time <= 0.001 * telemetry.end_time_ms
            match_ &= telemetry.channel == received_telemetry.template.get_full_name()
            if telemetry.expected_value != None:
                if telemetry.is_regex:
                    match_ &= re.search(telemetry.expected_value, str(received_telemetry.get_display_text())) != None
                else:
                    match_ &= telemetry.expected_value == received_telemetry.get_display_text()
            if match_:
                return received_telemetry
        return None


    def validate_sequence(self, seq: Sequence, starting_time: float) -> bool:
        success = True

        print(f"{' [VALIDATING EVENTS] ':-^80s}")

        for expected_event in seq.event_instrs:
            matching_event = self.find_matching_event(expected_event, starting_time)
            success &= (matching_event != None) == expected_event.is_expected
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
            result = f"{make_green('[OK]') if (matching_event != None) == expected_event.is_expected else make_red('[FAIL]')}"
            print(f"{timing} {event}{value}: {result} ~> {match_}")

        print()
        print(f"{' [VALIDATING TELEMETRY] ':-^80s}")

        for expected_telemetry in seq.telemetry_instrs:
            matching_telemetry = self.find_matching_telemetry(expected_telemetry, starting_time)
            success &= (matching_telemetry != None) == expected_telemetry.is_expected
            if matching_telemetry != None:
                timing = f"[{round(1000 * (matching_telemetry.get_time().get_float() - starting_time))} ms]"
                name = matching_telemetry.template.get_full_name()
                value = "" if matching_telemetry.get_display_text() == "" else f"\"{matching_telemetry.get_display_text()}\""
                match_ = f"{timing} {name} {value}"
            else:
                match_ = "None"
            timing = f"[{expected_telemetry.start_time_ms}:{expected_telemetry.end_time_ms}]"
            event = f"EXPECT{'' if expected_telemetry.is_expected else ' NO'} TELEMETRY {expected_telemetry.channel}"
            value = "" if expected_telemetry.expected_value == None else f" {'re' if expected_telemetry.is_regex else ''}\"{expected_telemetry.expected_value}\""
            result = f"{make_green('[OK]') if (matching_telemetry  != None) == expected_telemetry.is_expected else make_red('[FAIL]')}"
            print(f"{timing} {event}{value}: {result} ~> {match_}")

        return success
