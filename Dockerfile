# build stage
FROM node:slim AS build-stage

RUN yarn global add typescript jest
WORKDIR /usr/local/src/neodash

COPY ./package.json ./package.json
RUN yarn install
COPY . ./
RUN yarn run build-minimal


WORKDIR /usr/local/src/neodash
ENTRYPOINT [ "yarn", "run", "dev" ]