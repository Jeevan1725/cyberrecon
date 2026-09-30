\# Sequence Diagram — Command Flow



```mermaid

sequenceDiagram

&#x20;   participant OP as Operator CLI

&#x20;   participant C2 as C2 Server

&#x20;   participant QC as QR Channel

&#x20;   participant VC as Victim Client

&#x20;   participant H as Command Handler

&#x20;   participant EX as Exfil Endpoint



&#x20;   OP->>C2: POST /command/<id><br/>X-Operator-Token

&#x20;   C2->>C2: Verify token

&#x20;   C2->>C2: Queue command

&#x20;   C2-->>OP: 200 queued



&#x20;   loop Poll every 5s

&#x20;       VC->>C2: GET /qr/<id>

&#x20;       C2->>QC: Encode command as QR PNG

&#x20;       QC-->>VC: PNG image

&#x20;       VC->>VC: Selenium renders in Chrome

&#x20;       VC->>VC: OpenCV decodes QR

&#x20;   end



&#x20;   VC->>H: dispatch command

&#x20;   H->>H: Execute (e.g., screenshot)

&#x20;   H->>EX: POST /exfil/<id><br/>{type, data}

&#x20;   EX->>C2: Store exfil data

&#x20;   C2-->>EX: 200 received



&#x20;   OP->>C2: GET /exfil-data/<id>

&#x20;   C2-->>OP: JSON payload

```

