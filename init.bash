#!/bin/bash
# for local machine setup.
sudo apt update
# ansible dependency installation
sudo apt install software-properties-common --yes
# ansible installation
sudo add-apt-repository --yes --update ppa:ansible/ansible
sudo apt install ansible --yes
