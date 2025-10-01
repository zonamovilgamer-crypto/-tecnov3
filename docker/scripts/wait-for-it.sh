#!/bin/sh
# wait-for-it.sh

TIMEOUT=15
QUIET=0
STRICT=0
HOST=
PORT=
CMD=

usage() {
  cat << USAGE >&2
Usage:
  $0 host:port [-t timeout] [-s] [-- command args]
  $0 -h | --help
    -h | --help          Show this help and exit
    -q | --quiet         Don't output any status messages
    -s | --strict        Only execute subcommand if the test succeeds
    -t | --timeout TIMEOUT
                         Timeout in seconds, zero for no timeout
    -- COMMAND ARGS      Execute command with args after the test finishes
USAGE
  exit 1
}

wait_for() {
  for i in $(seq $TIMEOUT) ; do
    if [ $QUIET -ne 1 ]; then echo "Waiting for $HOST:$PORT..." ; fi
    if nc -z $HOST $PORT; then
      if [ $? -eq 0 ]; then
        if [ $QUIET -ne 1 ]; then echo "Connected to $HOST:$PORT." ; fi
        return 0
      fi
    fi
    sleep 1
  done
  if [ $QUIET -ne 1 ]; then echo "Timeout occurred after waiting $TIMEOUT seconds for $HOST:$PORT." ; fi
  return 1
}

while [ $# -gt 0 ]
do
  case "$1" in
    *:* )
    HOST=$(printf "%s\n" "$1"| cut -d : -f 1)
    PORT=$(printf "%s\n" "$1"| cut -d : -f 2)
    shift
    ;;
    -h | --help)
    usage
    ;;
    -q | --quiet)
    QUIET=1
    shift
    ;;
    -s | --strict)
    STRICT=1
    shift
    ;;
    -t | --timeout)
    TIMEOUT="$2"
    if [ $TIMEOUT -le 0 ]; then
      TIMEOUT=0
    fi
    shift 2
    ;;
    --)
    shift
    CMD="$@"
    break
    ;;
    * )
    usage
    ;;
  esac
done

if [ "$HOST" = "" -o "$PORT" = "" ]; then
  usage
fi

wait_for
RESULT=$?

if [ $STRICT -eq 1 ]; then
  if [ $RESULT -ne 0 ]; then
    exit $RESULT
  fi
fi

if [ "$CMD" != "" ]; then
  exec $CMD
fi
