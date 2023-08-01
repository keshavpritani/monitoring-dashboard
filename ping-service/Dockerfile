FROM 348221620929.dkr.ecr.us-east-1.amazonaws.com/base/status:staging-new

WORKDIR /app

ENV PATH /app:$PATH

COPY . /app
RUN chmod +x /app/command.sh

EXPOSE 80

CMD ["command.sh"]
