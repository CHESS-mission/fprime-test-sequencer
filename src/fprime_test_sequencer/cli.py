#!/usr/bin/env python3

import os
import argparse
import platform
from pathlib import Path

from fprime_gds.common.pipeline.standard import StandardPipeline
from fprime_gds.common.testing_fw.api import IntegrationTestAPI
from fprime_gds.common.utils.config_manager import ConfigManager
from fprime_gds.executables.utils import find_dict, get_artifacts_root

from fprime_test_sequencer.parser.exceptions import ParseError
from fprime_test_sequencer.parser.lexer import FileReader, Lexer
from fprime_test_sequencer.parser.parser import Parser, Sequence
from fprime_test_sequencer.sequencer import Sequencer, make_green, make_red


def find_dictionary() -> Path | None:
    detected_toolchain = get_artifacts_root() / platform.system()

    if not detected_toolchain.exists():
        print(f"{detected_toolchain} does not exist. Make sure to build.")
        return None

    likely_deployment = detected_toolchain / Path.cwd().name
    # Check if the deployment exists
    if likely_deployment.exists():
        deployment = likely_deployment
    else :
        child_directories = [child for child in detected_toolchain.iterdir() if child.is_dir()]

        if not child_directories:
            print(f"No deployments found in {detected_toolchain}. Specify deployment with: --deployment")
            return None
        if len(child_directories) > 1:
            print(f"Multiple deployments found in {detected_toolchain}. Choose using: --deployment")
            return None

        # Works for the old structure where the bin, lib, and dict directories live immediately under the platform
        if len(child_directories) == 3 and set([path.name for path in child_directories]) == {"bin", "lib", "dict"}:
            deployment = detected_toolchain
        else:
            deployment = child_directories[0]

    return find_dict(deployment)


def parse_file(file: str) -> dict[str, Sequence]:
    try:
        reader = FileReader(file)
    except FileNotFoundError:
        print(f"File not found: {file}")
        exit()

    lexer = Lexer(reader)
    parser = Parser(lexer)

    sequences = None
    try:
        sequences = parser.parse()
    except ParseError as pe:
        print(pe)

    if sequences == None:
        exit()

    return sequences


def check(file: str):
    sequences = parse_file(file)

    print(f"Syntax check [{make_green('OK')}]")

    i = 1
    for seq_name, seq in sequences.items():
        print(f"\n{i}.")
        header = f" [SEQUENCE {seq_name}] "
        print(f"{header:=^80s}")
        print(f"  is_test: {seq.is_test}")
        print(f"  duration: {seq.get_duration()} ms")

        print(f"{' [COMMANDS] ':-^80s}")
        for command_instr in seq.get_ordered_commands():
            print(f"  [{command_instr.send_time_ms} ms]: {command_instr.command} {' '.join(command_instr.args)}")

        print(f"{' [EVENTS] ':-^80s}")
        for event_instr in seq.event_instrs:
            timing = f"[{event_instr.start_time_ms}:{event_instr.end_time_ms}]"
            event = f"EXPECT{'' if event_instr.is_expected else ' NO'} EVENT {event_instr.event}"
            value = "" if event_instr.expected_value == None else f" {'re' if event_instr.is_regex else ''}\"{event_instr.expected_value}\""
            print(f"  {timing} {event}{value}")

        print(f"{' [TELEMETRY] ':-^80s}")
        for telemetry_instr in seq.telemetry_instrs:
            timing = f"[{telemetry_instr.start_time_ms}:{telemetry_instr.end_time_ms}]"
            event = f"EXPECT{'' if telemetry_instr.is_expected else ' NO'} TELEMETRY {telemetry_instr.channel}"
            value = "" if telemetry_instr.expected_value == None else f" {'re' if telemetry_instr.is_regex else ''}\"{telemetry_instr.expected_value}\""
            print(f"  {timing} {event}{value}")

        print(f"{'-'*80}")
        i += 1


def setup_integration_test_api(dictionary: str, file_storage_dir: str, tts_addr: str, tts_port: str) -> IntegrationTestAPI:
    pipeline = StandardPipeline()
    try:
        pipeline.setup(config=ConfigManager(), dictionary=dictionary, file_store=file_storage_dir)
        pipeline.connect(f"{tts_addr}:{tts_port}")
    except Exception:
        # In all error cases, pipeline should be shutdown before continuing with exception handling
        try:
            pipeline.disconnect()
        finally:
            raise

    api = IntegrationTestAPI(pipeline)
    api.setup()

    return api


def add_cli_arguments(parser: argparse.ArgumentParser):
    parser.add_argument("file", help="fpseq file from which sequences are read")
    parser.add_argument("--check", action="store_true", help="perform syntax check and print parsed sequences")
    parser.add_argument("--test", help="only run TEST")
    parser.add_argument("--dictionary", help="path to dictionary")
    parser.add_argument("--file-storage-directory", help="directory to store uplink and downlink files [default: /tmp/updown]", default="/tmp/updown")
    parser.add_argument("--tts-addr", help="threaded TCP socket server address [default: 0.0.0.0]", default="0.0.0.0")
    parser.add_argument("--tts-port", help="threaded TCP socket server port [default: 50050]", default="50050")


def main():
    parser = argparse.ArgumentParser()
    add_cli_arguments(parser)
    args = parser.parse_args()

    if args.check:
        check(args.file)
        exit()

    sequences = parse_file(args.file)

    if args.dictionary is None:
        print("Automatically detecting dictionary file...")
        args.dictionary = find_dictionary()
        if args.dictionary is None:
            print("Couldn't detect dictionary")
            exit()
    elif not os.path.exists(args.dictionary):
        print(f"Dictionary file {args.dictionary} does not exist")
        exit()

    print(f"Using dictionary {args.dictionary}")

    api = setup_integration_test_api(str(args.dictionary), args.file_storage_directory, args.tts_addr, args.tts_port)

    sequencer = Sequencer(api)

    test_count = 0
    successes = 0
    if args.test is not None:
        if args.test not in sequences.keys():
            print(f"No test named {args.test} in {args.file}")
            exit()
        print()
        success = sequencer.run_and_validate_sequence(sequences[args.test])
        test_count = 1
        successes = 1 if success else 0
    else:
        for sequence in sequences.values():
            if sequence.is_test:
                print(f"\n{test_count+1}.")
                success = sequencer.run_and_validate_sequence(sequence)
                test_count += 1
                successes += 1 if success else 0

    success_rate = f" [{successes}/{test_count} TESTS PASSED ({float(successes)/float(test_count):.0%})] "
    print(f"\n{make_green(success_rate) if successes == test_count else make_red(success_rate):=^89s}")

    api.pipeline.disconnect()


if __name__ == "__main__":
    main()
