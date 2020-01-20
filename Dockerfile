FROM python:3
# First copy requirements into tmp and pip-install them to allow better caching, apparently
COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt
# Change dir and copy source
WORKDIR /opt/jvm-loss
COPY . /opt/jvm-loss/

CMD ["python", "/opt/jvm-loss/mailclient.py"]
