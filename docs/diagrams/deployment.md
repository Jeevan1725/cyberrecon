\# Deployment Diagram



```mermaid

graph TB

&#x20;   subgraph "Attacker VM (Linux)"

&#x20;       DOCKER\[Docker Host]

&#x20;       C2\[C2 Server Container<br/>Port 8443<br/>Non-root user]

&#x20;       RELAY\[AWS Relay Container<br/>Port 443]



&#x20;       DOCKER --> C2

&#x20;       DOCKER --> RELAY

&#x20;       RELAY -.->|proxy| C2

&#x20;   end



&#x20;   subgraph "Victim VM (Windows)"

&#x20;       RATC\[RAT Client<br/>Python 3.11+]

&#x20;       CHROME\[Headless Chrome<br/>Selenium]

&#x20;       CAM\[Webcam Device]

&#x20;       FS\[File System]



&#x20;       RATC --> CHROME

&#x20;       RATC --> CAM

&#x20;       RATC --> FS

&#x20;   end



&#x20;   C2 -->|HTTPS<br/>QR PNG| CHROME

&#x20;   RATC -->|HTTPS<br/>POST /exfil| C2



&#x20;   subgraph "GitHub"

&#x20;       CI\[CI Workflow<br/>Bandit+pip-audit+Ruff+pytest]

&#x20;       CD\[CD Workflow<br/>Docker build+release]

&#x20;   end

```

