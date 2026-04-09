# DriveSafe Deployment Guide

## Production Deployment

This guide covers deploying DriveSafe to various environments.

## Prerequisites

- Docker & Docker Compose
- Kubernetes (for K8s deployment)
- GPU support (optional but recommended for better performance)
- Camera device access

## Local Deployment

### Development

```bash
# Setup environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Download models
python setup_models.py

# Run application
streamlit run app.py
```

### Production Local

```bash
# Use systemd service
sudo tee /etc/systemd/system/drivesafe.service > /dev/null <<EOF
[Unit]
Description=DriveSafe Driver Drowsiness Detection
After=network.target

[Service]
Type=simple
User=drivesafe
WorkingDirectory=/opt/drivesafe
ExecStart=/opt/drivesafe/venv/bin/streamlit run app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl enable drivesafe
sudo systemctl start drivesafe
sudo systemctl status drivesafe
```

## Docker Deployment

### Build Image

```bash
# Build production image
docker build -t drivesafe:latest .

# Build with specific Python version
docker build --build-arg PYTHON_VERSION=3.11 -t drivesafe:py311 .

# Build for different architectures
docker buildx build --platform linux/amd64,linux/arm64 -t drivesafe:latest .
```

### Run Container

```bash
# Basic run
docker run -it --device /dev/video0 -p 8501:8501 drivesafe:latest

# With persistent storage
docker run -d \
  --name drivesafe \
  --device /dev/video0 \
  -p 8501:8501 \
  -v /home/user/drivesafe_logs:/app/logs \
  -v /home/user/drivesafe_data:/app/data \
  --restart unless-stopped \
  drivesafe:latest

# With GPU support (NVIDIA)
docker run -d \
  --name drivesafe \
  --gpus all \
  --device /dev/video0 \
  -p 8501:8501 \
  drivesafe:latest

# With environment variables
docker run -d \
  --name drivesafe \
  --device /dev/video0 \
  -p 8501:8501 \
  -e LOG_LEVEL=INFO \
  -e SOS_ENABLED=false \
  -e ENABLE_AUDIO_ALERTS=true \
  drivesafe:latest
```

### Docker Compose

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f drivesafe

# Stop services
docker-compose down

# Remove volumes
docker-compose down -v
```

## Kubernetes Deployment

### Create Namespace

```bash
kubectl create namespace drivesafe
```

### ConfigMap and Secrets

```yaml
# Create ConfigMap
apiVersion: v1
kind: ConfigMap
metadata:
  name: drivesafe-config
  namespace: drivesafe
data:
  LOG_LEVEL: "INFO"
  ENABLE_AUDIO_ALERTS: "true"

---
# Create Secret for sensitive data
apiVersion: v1
kind: Secret
metadata:
  name: drivesafe-secrets
  namespace: drivesafe
type: Opaque
stringData:
  SOS_API_KEY: "your-api-key-here"
  EMERGENCY_CONTACT: "+1234567890"
```

### Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: drivesafe
  namespace: drivesafe
spec:
  replicas: 1
  selector:
    matchLabels:
      app: drivesafe
  template:
    metadata:
      labels:
        app: drivesafe
    spec:
      containers:
      - name: drivesafe
        image: drivesafe:latest
        imagePullPolicy: IfNotPresent
        ports:
        - containerPort: 8501
        env:
        - name: LOG_LEVEL
          valueFrom:
            configMapKeyRef:
              name: drivesafe-config
              key: LOG_LEVEL
        - name: SOS_API_KEY
          valueFrom:
            secretKeyRef:
              name: drivesafe-secrets
              key: SOS_API_KEY
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2"
        livenessProbe:
          httpGet:
            path: /_stcore/health
            port: 8501
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /_stcore/health
            port: 8501
          initialDelaySeconds: 20
          periodSeconds: 5
        volumeMounts:
        - name: logs
          mountPath: /app/logs
        - name: data
          mountPath: /app/data
        - name: camera
          mountPath: /dev/video0
      volumes:
      - name: logs
        emptyDir: {}
      - name: data
        emptyDir: {}
      - name: camera
        hostPath:
          path: /dev/video0
          type: CharDevice
```

### Service

```yaml
apiVersion: v1
kind: Service
metadata:
  name: drivesafe
  namespace: drivesafe
spec:
  type: LoadBalancer
  selector:
    app: drivesafe
  ports:
  - port: 80
    targetPort: 8501
```

### Deploy to K8s

```bash
# Apply configuration
kubectl apply -f configmap.yaml
kubectl apply -f secret.yaml
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml

# Check deployment
kubectl get deployments -n drivesafe
kubectl get pods -n drivesafe
kubectl logs -f deployment/drivesafe -n drivesafe

# Port forward for local access
kubectl port-forward -n drivesafe service/drivesafe 8501:80
```

## Cloud Deployment

### AWS EC2

```bash
# Launch EC2 instance
aws ec2 run-instances \
  --image-id ami-0c55b159cbfafe1f0 \
  --instance-type t3.medium \
  --key-name my-key \
  --security-groups drivesafe-sg

# SSH into instance
ssh -i my-key.pem ubuntu@<instance-IP>

# Install Docker
sudo apt-get update
sudo apt-get install docker.io -y
sudo usermod -aG docker ubuntu

# Clone and deploy
git clone <repo-url>
cd prj
docker-compose up -d
```

### AWS ECS (Elastic Container Service)

```bash
# Create ECS cluster
aws ecs create-cluster --cluster-name drivesafe

# Register task definition
aws ecs register-task-definition --cli-input-json file://task-definition.json

# Run service
aws ecs create-service \
  --cluster drivesafe \
  --service-name drivesafe-service \
  --task-definition drivesafe:1 \
  --desired-count 1
```

### Google Cloud Run

```bash
# Build and push to Container Registry
docker build -t gcr.io/<project-id>/drivesafe:latest .
docker push gcr.io/<project-id>/drivesafe:latest

# Deploy to Cloud Run
gcloud run deploy drivesafe \
  --image gcr.io/<project-id>/drivesafe:latest \
  --platform managed \
  --region us-central1 \
  --memory 2Gi \
  --cpu 2
```

### Azure Container Instances

```bash
# Build and push to Azure Container Registry
az acr build --registry <registry-name> --image drivesafe:latest .

# Deploy to Container Instances
az container create \
  --resource-group <group-name> \
  --name drivesafe \
  --image <registry-name>.azurecr.io/drivesafe:latest \
  --cpu 2 \
  --memory 2 \
  --ports 8501 \
  --environment-variables LOG_LEVEL=INFO
```

## Monitoring

### Prometheus Metrics

```bash
# Start Prometheus
docker run -d \
  -p 9090:9090 \
  -v $(pwd)/prometheus.yml:/etc/prometheus/prometheus.yml \
  prom/prometheus
```

### Grafana Dashboard

```bash
# Start Grafana
docker run -d \
  -p 3000:3000 \
  -e GF_SECURITY_ADMIN_PASSWORD=admin \
  grafana/grafana

# Add Prometheus data source
# URL: http://prometheus:9090
```

### Log Aggregation (ELK Stack)

```docker-compose
version: '3'
services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:7.13.0
    environment:
      - discovery.type=single-node
    ports:
      - "9200:9200"

  logstash:
    image: docker.elastic.co/logstash/logstash:7.13.0
    volumes:
      - ./logstash.conf:/usr/share/logstash/pipeline/logstash.conf
    ports:
      - "5000:5000"

  kibana:
    image: docker.elastic.co/kibana/kibana:7.13.0
    ports:
      - "5601:5601"
```

## Performance Optimization

### GPU Acceleration

```python
# Use TensorFlow with GPU
import tensorflow as tf
print(tf.config.list_physical_devices('GPU'))

# CUDA configuration in Dockerfile
ENV CUDA_VISIBLE_DEVICES=0
```

### Load Balancing

```nginx
upstream drivesafe {
    server localhost:8501;
    server localhost:8502;
    server localhost:8503;
}

server {
    listen 80;
    location / {
        proxy_pass http://drivesafe;
    }
}
```

## Security

### SSL/TLS

```bash
# Generate self-signed certificate
openssl req -x509 -newkey rsa:4096 -nodes \
  -out cert.pem -keyout key.pem -days 365

# Use in Streamlit configuration
[server]
sslCertFile = /path/to/cert.pem
sslKeyFile = /path/to/key.pem
```

### Network Security

```bash
# Firewall rules
sudo ufw allow 8501/tcp
sudo ufw allow 8501/udp
```

## Backup & Recovery

```bash
# Backup data
tar -czf drivesafe_backup.tar.gz logs/ data/

# Restore data
tar -xzf drivesafe_backup.tar.gz

# S3 backup
aws s3 sync ./data s3://drivesafe-bucket/backups/
aws s3 sync ./logs s3://drivesafe-bucket/logs/
```

## Troubleshooting

### Cannot access camera in Docker
```bash
# Grant camera device permissions
docker run --device /dev/video0:/dev/video0 ...
```

### Memory issues
```bash
# Increase container memory limit
docker run -m 4g ...
```

### GPU not detected
```bash
# Verify GPU drivers
nvidia-smi

# Run with GPU support
docker run --gpus all ...
```

## Rollback

```bash
# Docker Compose
docker-compose down
git checkout <previous-version>
docker-compose up -d

# Kubernetes
kubectl rollout undo deployment/drivesafe -n drivesafe
kubectl rollout status deployment/drivesafe -n drivesafe
```

---

For more information, see README.md
