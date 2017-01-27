#!/bin/bash
#
# watchdog
#
# Run as a cron job to keep an eye on what_to_monitor which should always
# be running. Restart what_to_monitor and send notification as needed.
#
# This needs to be run as root or a user that can start system services.

NAME="button.py"
START="/usr/bin/python /home/pi/button.py"
NOTIFY=''
NOTIFYCC=''
MAIL=/usr/bin/mail
PGREP=/usr/bin/pgrep

result=$($PGREP -fc $NAME)
echo $result
if [ $result -eq 0 ]; then
   echo "The script $NAME is NOT RUNNING. Starting $NAME and sending notices."
   $START 2>&1 >/dev/null &
   echo "The script $NAME was not running on $HOSTNAME. The watchdog started it." | $MAIL -s "Watchdog Notice on $HOSTNAME" $NOTIFYCC $NOTIFY
fi

exit