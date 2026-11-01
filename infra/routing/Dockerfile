# GraphHopper for Verst (ADR-0017). Upstream publishes no official image (README "Docker": only a community
# image built daily from master), so we build our own from the pinned Maven Central jar.
FROM eclipse-temurin:21.0.12_8-jre-noble

ARG GH_VERSION=11.0
ARG GH_SHA256=b59c024afe172ec6ec85b6327006c3138ec58c7d0bcd26253d0e42853f613def

# curl: the jar, the health check and build_graph.sh; osmium-tool + python3: build_graph.sh (merge, build.json).
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl osmium-tool python3 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /srv/graphhopper
RUN curl -fsSL --retry 5 -o graphhopper-web.jar \
      "https://repo1.maven.org/maven2/com/graphhopper/graphhopper-web/${GH_VERSION}/graphhopper-web-${GH_VERSION}.jar" \
 && echo "${GH_SHA256}  graphhopper-web.jar" | sha256sum -c -

COPY config.yml build_graph.sh ./
COPY custom_models ./custom_models
# D-IR-21: a small VM serves the graph from disk (MMAP, 1 GB heap) instead of the heap; GH_CONFIG=config-mmap.yml.
# A separate file because Dropwizard ignores -Ddw.graphhopper.graph.dataaccess.default_type (dotted flat key).
RUN sed 's/^  graph.dataaccess.default_type: RAM_STORE$/  graph.dataaccess.default_type: MMAP/' config.yml > config-mmap.yml \
 && grep -q 'default_type: MMAP' config-mmap.yml

RUN useradd --system --uid 10001 graphhopper && mkdir -p /data && chown graphhopper /data
USER graphhopper

# /data/current/graph-cache is the graph the server loads; build_graph.sh writes a new one to /data/next
# (README.md "Weekly rebuild"). JAVA_OPTS comes from docker-compose.yml.
ENV JAVA_OPTS="-Xmx8g -Xms8g" GH_CONFIG=config.yml
EXPOSE 8989 8990
HEALTHCHECK --interval=30s --timeout=5s --start-period=10m CMD curl -fs http://127.0.0.1:8989/health || exit 1
ENTRYPOINT ["sh", "-c", "exec java $JAVA_OPTS -Ddw.graphhopper.datareader.file=/data/current/osm/region.osm.pbf -Ddw.graphhopper.graph.location=/data/current/graph-cache -jar graphhopper-web.jar server $GH_CONFIG"]
