\# Use Case Diagram



```mermaid

graph TB

&#x20;   subgraph Actors

&#x20;       OP\[👤 Operator]

&#x20;       DF\[🛡️ Defender]

&#x20;       VM\[💻 Victim Host]

&#x20;   end



&#x20;   subgraph "CyberRecon System"

&#x20;       UC1\[Register Victim]

&#x20;       UC2\[Send Command]

&#x20;       UC3\[Fetch QR Command]

&#x20;       UC4\[Execute RAT Command]

&#x20;       UC5\[Exfiltrate Data]

&#x20;       UC6\[View Dashboard]

&#x20;       UC7\[Download Exfil ZIP]

&#x20;       UC8\[Authenticate Operator]

&#x20;       UC9\[Parse NL Command]

&#x20;   end



&#x20;   OP --> UC1

&#x20;   OP --> UC2

&#x20;   OP --> UC6

&#x20;   OP --> UC7

&#x20;   OP --> UC8

&#x20;   OP --> UC9



&#x20;   VM --> UC3

&#x20;   VM --> UC4

&#x20;   VM --> UC5



&#x20;   DF -.->|reads IOCs| UC9



&#x20;   UC2 -.->|requires| UC8

&#x20;   UC7 -.->|requires| UC8

&#x20;   UC4 -.->|triggers| UC5

```

