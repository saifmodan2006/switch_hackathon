# MinIO's historical public binary/image distribution is no longer available.
# Build the unchanged official AGPL source at the immutable release commit.
FROM golang:1.24-alpine AS build
RUN apk add --no-cache git
WORKDIR /src
RUN git init && git remote add origin https://github.com/minio/minio.git \
 && git fetch --depth 1 origin f19c534b9f457773dcd043d977433e1a71525c3b \
 && git checkout FETCH_HEAD
RUN CGO_ENABLED=0 go build -trimpath -o /minio .
FROM alpine:3.22
RUN apk add --no-cache ca-certificates && adduser -D -u 10001 minio \
 && mkdir /data /licenses && chown minio:minio /data
COPY --from=build /minio /usr/local/bin/minio
COPY --from=build /src/LICENSE /licenses/MINIO-AGPLv3
USER minio
EXPOSE 9000 9001
ENTRYPOINT ["minio"]
