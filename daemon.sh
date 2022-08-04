#!/bin/bash

while :
do
	source env.sh
	python example.py
	echo "Press once <CTRL+C> to check now, and twice to exit before next loop."
	hour=0
	min=30
	sec=0
	trap -- "hour=0;min=0;sec=0;" INT
	while [ $hour -ge 0 ]; do
		while [ $min -ge 0 ]; do
			while [ $sec -gt 0 ]; do
				echo -ne "$(printf "%02d:%02d:%02d" $hour $min $sec)\033[0K\r"
				let "sec=sec-1"
				sleep 1
			done
			sec=59
			let "min=min-1"
		done
		min=59
		let "hour=hour-1"
	done
	trap INT
done
