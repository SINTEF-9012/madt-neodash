# build stage
FROM node AS build-stage

RUN yarn global add typescript jest
WORKDIR /usr/local/src/neodash

# Pull source code if you have not cloned the repository
#RUN apk add --no-cache git
#RUN git clone https://github.com/neo4j-labs/neodash.git /usr/local/src/neodash

# Copy sources and install/build



ENV PATH="/root/miniconda3/bin:${PATH}"
ARG PATH="/root/miniconda3/bin:${PATH}"
RUN arch=$(uname -m) && \
    if [ "$arch" = "x86_64" ]; then \
    MINICONDA_URL="https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh"; \
    elif [ "$arch" = "aarch64" ]; then \
    MINICONDA_URL="https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-aarch64.sh"; \
    else \
    echo "Unsupported architecture: $arch"; \
    exit 1; \
    fi && \
    wget $MINICONDA_URL -O miniconda.sh && \
    mkdir -p /root/.conda && \
    bash miniconda.sh -b -p /root/miniconda3 && \
    rm -f miniconda.sh

# ENV PATH /opt/conda/bin:$PATH
RUN conda update conda
# RUN conda update anaconda
RUN conda update --all
RUN conda config --append channels conda-forge
    
COPY ./connection/environment.yml ./connection/environment.yml
RUN conda env create -f ./connection/environment.yml

# COPY ./connection/requirements.txt ./connection/requirements.txt
# RUN pip install -r ./connection/requirements.txt

COPY ./package.json ./package.json
RUN yarn install
COPY . ./
RUN yarn run build-minimal




# # production stage
# FROM nginx:alpine AS neodash
# RUN apk upgrade
# COPY --from=build-stage /usr/local/src/neodash/dist /usr/share/nginx/html

# COPY ./conf/default.conf /etc/nginx/conf.d/
# COPY ./scripts/config-entrypoint.sh /docker-entrypoint.d/config-entrypoint.sh
# COPY ./scripts/message-entrypoint.sh /docker-entrypoint.d/message-entrypoint.sh

# RUN chown -R nginx:nginx /var/cache/nginx && \
#     chown -R nginx:nginx /var/log/nginx && \
#     chown -R nginx:nginx /etc/nginx/conf.d && \
#     chown -R nginx:nginx /docker-entrypoint.d/config-entrypoint.sh && \
#     chmod +x /docker-entrypoint.d/config-entrypoint.sh  && \
#     chmod +x /docker-entrypoint.d/message-entrypoint.sh
# RUN touch /var/run/nginx.pid && \
#     chown -R nginx:nginx /var/run/nginx.pid
# RUN chown -R nginx:nginx /usr/share/nginx/html/

# ## Launch webserver as non-root user.
# USER nginx
# EXPOSE 5005
# HEALTHCHECK cmd curl --fail http://localhost:5005 || exit 1
# LABEL version="2.2.5"

WORKDIR /usr/local/src/neodash
ENTRYPOINT [ "/bin/bash", "start.sh" ]
