# dev
docker pull 348221620929.dkr.ecr.us-east-1.amazonaws.com/base/status:staging-new
docker tag 348221620929.dkr.ecr.us-east-1.amazonaws.com/base/status:staging-new 468060833953.dkr.ecr.us-east-1.amazonaws.com/base/status:dev
docker push 468060833953.dkr.ecr.us-east-1.amazonaws.com/base/status:dev


# prod
docker pull 348221620929.dkr.ecr.us-east-1.amazonaws.com/base/status:staging-new
docker tag 348221620929.dkr.ecr.us-east-1.amazonaws.com/base/status:staging-new 300980071293.dkr.ecr.ap-southeast-1.amazonaws.com/base/status:prod 
docker push  300980071293.dkr.ecr.ap-southeast-1.amazonaws.com/base/status:prod
