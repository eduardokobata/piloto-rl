set -e

IMAGE_NAME="fsd-laptime-simulator"


docker build -t $IMAGE_NAME .


docker run --rm \
    --user "$(id -u):$(id -g)" \
    -v "$PWD:/app" \
    $IMAGE_NAME

