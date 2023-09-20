#!/bin/bash
ip route | grep 'linkdown' | awk '{print $1}' | while read -r line; do
    echo "Deleting route: $line"  # Display the route being deleted
    ip route del $line  # Delete the route
done
