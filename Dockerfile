ARG DOCKER_REGISTRY=base
ARG APPNAME=base
ARG TAGNAME=base
FROM ${DOCKER_REGISTRY}/base/status:${TAGNAME}

ARG APPNAME

WORKDIR /app

ENV PATH /app:$PATH
ENV APPNAME $APPNAME
COPY ${APPNAME}-service/ /app/
COPY command.sh /app
RUN chmod +x /app/command.sh

# ADD ./rsyslog.conf /etc/rsyslog.conf

EXPOSE 8000

CMD ["command.sh"]
