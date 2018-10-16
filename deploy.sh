#!/bin/bash
export HOST_IP=<HOST_IP>
cd <PATH_TO_REPOSITORY>
docker-compose scale slackops=0
docker rm $(docker ps -q -f status=exited)
docker rmi -f swiftops/slackops:latest && docker pull swiftops/slackops:latest && docker-compose up -d --remove-orphans