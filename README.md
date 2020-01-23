# jvm-loss
The JVM(Java Vending Machine) at Strandvejen may experience some loss(making coffee without paying). This project aims to calculate this loss from sales-reporting from the network-enabled coffee-machine and by comparing with the stregsystem sales-database.

## Usage
1. Download the credentials.json for fklub.jvmloss@gmail.com
1. Run `mailclient.py`, allowing potential authorisation-requests in web-browser
1. Consider that this is immensely WIP and prone to break

Alternatively, build a Docker image and run it with the following commands. Note that you have to embed the authentication into the Docker `credentials.json` and `token.pickle`.
1. `docker build --tag=jvm-loss .`
1. `docker run --name jvm-loss -it jvm-loss` Optionally specify the `--rm` flag, which removes the container upon stopping it.
