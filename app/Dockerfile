FROM python:3.12-alpine
ARG APP_VERSION=1.0.0
ENV APP_VERSION=${APP_VERSION}
RUN adduser -D appuser
WORKDIR /srv
COPY app.py .
USER appuser
EXPOSE 8080
CMD ["python", "app.py"]
