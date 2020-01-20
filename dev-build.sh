#!/bin/bash

# Pull, exiting if failure
git pull || exit 1

# FIXME, remove previous images? :latest should be sufficient
printf "### VCS cleared. Continuing flow\n"

# Build new image from Dockerfile
printf "### Building new 'cogi/jvm-loss' image\n"
sudo docker build -t cogi/jvm-loss .

# Stop running images based on 'cogi/jvm-loss'
printf "### Stopping all containers which are ancestors of 'cogi/jvm-loss'\n" 
sudo docker ps -qf ancestor=cogi/jvm-loss | xargs -r sudo docker stop

# Forcefully remove any containers named 'jvm-loss'
printf "### Removing any container named 'jvm-loss'\n"
sudo docker ps -qaf name=jvm-loss | xargs -r sudo docker rm -f 

# Run and attach to new image, to detach without killing process use [Ctrl+p] [Ctrl+q]
printf "### Running new 'cogi/jvm-loss' image\n"
sudo docker run --name jvm-loss -it cogi/jvm-loss:latest
