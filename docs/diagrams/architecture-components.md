\# Component Diagram



```mermaid

graph LR

&#x20;   subgraph "Operator Side"

&#x20;       CLI\[Operator CLI]

&#x20;       DASH\[Dashboard]

&#x20;   end



&#x20;   subgraph "C2 Server"

&#x20;       API\[Flask REST API]

&#x20;       QR\[QR Encoder]

&#x20;       STORE\[(In-memory<br/>victim store)]

&#x20;       AUTH\[Token Auth]

&#x20;   end



&#x20;   subgraph "Victim Side"

&#x20;       RAT\[RAT Client]

&#x20;       BROWSER\[Headless Chrome]

&#x20;       DECODER\[OpenCV Decoder]

&#x20;       MODULES\[6 Feature Modules]

&#x20;   end



&#x20;   subgraph "Optional"

&#x20;       RELAY\[AWS Relay]

&#x20;       AI\[AI Agent]

&#x20;   end



&#x20;   CLI -->|HTTP| AUTH

&#x20;   DASH -->|HTTP poll| API

&#x20;   AUTH --> API

&#x20;   API --> STORE

&#x20;   API --> QR

&#x20;   QR -->|PNG| BROWSER

&#x20;   BROWSER --> DECODER

&#x20;   DECODER --> RAT

&#x20;   RAT --> MODULES

&#x20;   MODULES -->|POST /exfil| API

&#x20;   CLI -.->|via| RELAY

&#x20;   AI -.->|NL parse| CLI

```

