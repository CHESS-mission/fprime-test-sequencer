# F´ Test Sequencer

Simple test sequencer for F´ based flight software with support for sending
commands and uplinking files at specific times, and expecting events or
telemetry with matching values during specific time intervals.

## Installation

Install the latest version of the F´ test sequencer directly from GitHub using pip:

```console
pip install git+https://github.com/CHESS-mission/fprime-test-sequencer.git
```

## The FpSeq format

The F´ Test Sequencer defines sequences using the `FpSeq` format described in
this section.

### Example

This is the [`example.fpseq`](./example.fpseq) file showcasing most of the
format's capabilities:

```python
# Write comments using '#'
# Create a test sequence called test1
TEST SEQ test1
  # Expect no event of severity warning_hi or fatal along the course of the test
  [:] EXPECT NO EVENT EventSeverity.WARNING_HI
  [:] EXPECT NO EVENT EventSeverity.FATAL

  # Send a command without arguments at the start of the test
  [0] COMMAND eventAction.LOG_VERSION
    # Any instruction can be followed by an indented block of instructions
    # to make their timing relative the the instruction's starting time
    # Note that indented blocks can be arbitrarily nested

    # Expect events in the next 100 ms after sending the command
    [:100] EXPECT EVENT cmdDisp.OpCodeDispatched re"0xe04"
    # Use re"<expr>" to match the received value against the regular expression <expr>
    [:100] EXPECT EVENT eventAction.CurrentVersion re"Current version : \d"
    [:100] EXPECT EVENT cmdDisp.OpCodeCompleted re"0xe04"

    # Expect telemetry in the next 15 seconds after sending the command
    [:15000] EXPECT TELEMETRY eventAction.Version re"\d"

  # Send a 2nd command 1 second after the start of the test
  [1000] COMMAND eventAction.SCHEDULE_NUMBER_CRUNCHER 5 600 60
    [:100] EXPECT EVENT cmdDisp.OpCodeDispatched re"0xe06"
    [:100] EXPECT EVENT cmdDisp.OpCodeCompleted re"0xe06"

    # Expect mode changes only during specific time interval
    [:4000] EXPECT NO EVENT eventAction.ModeChanged
    [4000:7000] EXPECT EVENT eventAction.ModeChanged "Mode set to MEASURE"
    [7000:64000] EXPECT NO EVENT eventAction.ModeChanged
    [64000:69000] EXPECT EVENT eventAction.ModeChanged "Mode set to CHARGE"

  # Start uplinking a file to the OBC 100 seconds after the start of the test
  [100000] UPLINK "/input/IOD_v2" "/home/root/executables/IOD_v2"
    # Expect the file to be received in the next 60 seconds
    [:60000] EXPECT EVENT fileUplink.FileReceived

  # Run another sequence inside a sequence 160 seconds after the start of the test
  [160000] RUNSEQ simple_seq

# Create a simple sequence called simple_seq
SEQ simple_seq
  [0] COMMAND eventAction.UPDATE "/home/root/executables/" "IOD_v2"
    [:100] EXPECT EVENT cmdDisp.OpCodeDispatched re"0xe03"
    [:100] EXPECT EVENT cmdDisp.OpCodeCompleted re"0xe03"

    [2000] COMMAND eventAction.SCHEDULE_RESTART 1
```

### Comments

Any text following a `#` on a line is considered a comment and ignored by the
lexer.

```python
# This is a comment
SEQ simple_seq # This is also a comment
```

### Litterals

A litteral is either a numerical value or a string of text inside double
quotes. The double quotes character `"` can be escaped using by prepending it
with another double quotes `""`. String litterals can also be regular
expressions, in which case they start with `re`.

```python
# These are all litterals
42
42.24
"42.24"
"Hello World!"
"Hello ""World""!"
re"^Hello .*!$"
```

### Keywords

The following identifiers are reserved FpSeq keywords:

| Keywords    |
| ----------- |
| `TEST`      |
| `SEQ`     |
| `EXPECT` |
| `NO`        |
| `COMMAND` |
| `EVENT`  |
| `TELEMETRY` |
| `UPLINK`  |
| `RUNSEQ` |

### Sequences

All `FpSeq` files start by declaring a sequence with the following syntax:

```python
SEQ <sequence-name>
    ... # Indented block of instruction
```

Where `<sequence-name>` is the unique name of the sequence.

A sequence is made up of an indented block of instructions following its
definition.

Sequences can also be marked as test sequences:

```python
TEST SEQ <sequence-name>
    ...
```

Test sequences are similar to simple sequences except that they will all be run
by default when no sequence is specified to the F´ Test sequencer.

An `FpSeq` file can contain any number of sequences.

### Command instructions

Command instructions send F´ commands to the flight software at specific times.
They are declared as follows:

```python
[<send-time>] COMMAND <command-name> <command-args>
```

Where:

- `<send-time>` is the relative time in miliseconds at which the command is to
be sent
- `<command-name>` is the name of the command as defined in the F´ dictionary
of the deployment
- `<command-args>` are any number of space separated litterals which will be
passed as arguments to the command.

> **_Note:_** the list of all the commands supported by an F´ deployment with
their arguments can be found by running `fprime-cli command-send --dictionary
<path-to-dictionary.xml> --list`.

### Uplink instructions

Uplink instructions send local files to the flight software at specific times.
They are declared as follows:

```python
[<start-time>] UPLINK <local-source> <remote-destination>
```

Where:

- `<start-time>` is the relative time in miliseconds at which the uplink is
to be initiated
- `<local-source>` is the path to the local file
- `<remote-destination>` is the remote destination path for the file

### Event instructions

Event instructions expect the reception of particular events during specific
time intervals. They are declared as follows:

```python
[<start-time>:<end-time>] EXPECT <NO> EVENT <event-name-or-severity> <value>
```

Where:

- `<start-time>` is the relative starting time of the interval in miliseconds.
Leaving blank is equivalent to setting it to `0`
- `<end-time>` is the relative ending time of the interval in miliseconds
Leaving blank is equivalent to setting it to the total duration of its block.
- `<NO>` is either the Keyword `NO` or blank, depending on whether the event is
expected or not
- `<event-name-or-severity>` is either the name or the severity of the event as
defined in the F´ dictionary of the deployment
- `<value>` is an optional litteral against which the value of the received
events will be matched

The different severity levels are the following (from the [F´ documentation](https://nasa.github.io/fprime/UsersGuide/user/cmd-evt-chn-prm.html)):

| Severity level            | Description                                                           |
| ------------------------- | --------------------------------------------------------------------- |
| EventSeverity.DIAGNOSTIC  | akin to debug messages. Usually not sent to the ground                |
| EventSeverity.ACTIVITY_LO | akin to fine info messages these typically come from background tasks |
| EventSeverity.ACTIVITY_HI | akin to info messages these typically come from foreground tasks      |
| EventSeverity.WARNING_LO  | less severe warning events                                            |
| EventSeverity.WARNING_HI  | high-severity warning events, although the system can still function  |
| EventSeverity.FATAL       | fatal events indicating that the system must reboot                   |
| EventSeverity.COMMAND     | events tracing the execution of commands                              |

> **_Note:_** the list of all the events sent by an F´ deployment can be found
by running `fprime-cli events --dictionary <path-to-dictionary.xml> --list`.

### Telemetry instructions

Telemetry instructions expect the reception of particular telemetry channels
during specific time intervals. They are declared as follows:

```python
[<start-time>:<end-time>] EXPECT <NO> TELEMETRY <channel-name> <value>
```

Where:

- `<start-time>` is the relative starting time of the interval in miliseconds.
Leaving blank is equivalent to setting it to `0`
- `<end-time>` is the relative ending time of the interval in miliseconds
Leaving blank is equivalent to setting it to the total duration of its block.
- `<NO>` is either the Keyword `NO` or blank, depending on whether the
telemetry is expected or not
- `<channel-name>` is the name the channel as defined in the F´ dictionary of
the deployment
- `<value>` is an optional litteral against which the value of the received
telemetry will be matched

> **_Note:_** the list of all the telemetry channels of an F´ deployment can be found
by running `fprime-cli channels --dictionary <path-to-dictionary.xml> --list`.

### Runseq instructions

Runseq instructions execute a sequence inside another sequence. They are
declared as follows:

```python
[<start-time>] RUNSEQ <sequence-name>
```

Where:

- `<start-time>` is the relative starting time of the inner sequence. All
timings of the inner sequence will be offset by this starting time
- `<sequence-name>` is the name the inner sequence to be run, as defined
anywhere in the `FpSeq` file

### Indentation

Any instruction can be followed by an indented block of instructions to make
their timing relative the the instruction's starting time. Indented blocks can
be arbitrarily nested. The absolute timing can be verified using
`fprime-test-sequencer --check`.

```python
SEQ indentation_example
  [1000] COMMAND eventAction.LOG_VERSION
    [700] COMMAND eventAction.SCHEDULE_NUMBER_CRUNCHER 5 600 60
      [:4000] EXPECT NO EVENT eventAction.ModeChanged
      [4000:7000] EXPECT EVENT eventAction.ModeChanged "Mode set to MEASURE"
      [7000:64000] EXPECT NO EVENT eventAction.ModeChanged
        [42] COMMAND eventAction.LOG_VERSION
      [64000:69000] EXPECT EVENT eventAction.ModeChanged "Mode set to CHARGE"
```

```console
$ fprime-test-sequencer --check indentation_example.fpseq 
Syntax check [OK]

1.
======================== [SEQUENCE indentation_example] ========================
  is_test: False
  duration: 70700 ms
---------------------------------- [COMMANDS] ----------------------------------
  [1000 ms]: eventAction.LOG_VERSION 
  [1700 ms]: eventAction.SCHEDULE_NUMBER_CRUNCHER 5 600 60
  [8742 ms]: eventAction.LOG_VERSION 
----------------------------------- [EVENTS] -----------------------------------
  [1700:5700] EXPECT NO EVENT eventAction.ModeChanged
  [5700:8700] EXPECT EVENT eventAction.ModeChanged "Mode set to MEASURE"
  [8700:65700] EXPECT NO EVENT eventAction.ModeChanged
  [65700:70700] EXPECT EVENT eventAction.ModeChanged "Mode set to CHARGE"
--------------------------------- [TELEMETRY] ----------------------------------
----------------------------------- [UPLINK] -----------------------------------
--------------------------------------------------------------------------------
```

## Usage

The `--help` option prints usage and exits:

```console
$ fprime-test-sequencer --help
usage: fprime-test-sequencer [-h] [-c] [-t TEST] [-d DICTIONARY] [--file-storage-directory FILE_STORAGE_DIRECTORY] [--tts-addr TTS_ADDR] [--tts-port TTS_PORT] [--log-all LOG_ALL_FILE] file

positional arguments:
  file                  fpseq file from which sequences are read

options:
  -h, --help            show this help message and exit
  -c, --check           perform syntax check and print parsed sequences
  -t TEST, --test TEST  only run TEST
  -d DICTIONARY, --dictionary DICTIONARY
                        path to dictionary
  --file-storage-directory FILE_STORAGE_DIRECTORY
                        directory to store uplink and downlink files [default: /tmp/updown]
  --tts-addr TTS_ADDR   fprime-gds threaded TCP socket server address [default: 0.0.0.0]
  --tts-port TTS_PORT   fprime-gds threaded TCP socket server port [default: 50050]
  --log-all LOG_ALL_FILE
                        log all sent commands, received events and telemetry to given file
```

By default, `fprime-test-sequencer` runs all test sequences from the given
`FpSeq` file. If `--check` is passed, then no sequence is run and only the
syntax of the file is verified and a breakdown of all found sequences is
printed with absolute timings. If `--test <TEST>` is passed, only the sequence
named `<TEST>` is executed.
