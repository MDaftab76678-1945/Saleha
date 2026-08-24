---
id: "doc_api_contracts"
title: "Enterprise OpenAPI 3.1 & gRPC Protocol Specifications"
version: "3.0.0"
---

# Enterprise API Contracts & Interface Governance

## 1. Protocol Buffers v3 Definition (East-West Microservices)
```protobuf
syntax = "proto3";

package enterprise.orders.v1;
option go_package = "github.com/enterprise/proto/orders/v1;ordersv1";

service OrderService {
  rpc CreateOrder (CreateOrderRequest) returns (CreateOrderResponse);
  rpc GetOrder (GetOrderRequest) returns (Order);
}

message CreateOrderRequest {
  string idempotency_key = 1;
  string user_id = 2;
  int64 amount_cents = 3;
  string currency = 4;
}

message CreateOrderResponse {
  string order_id = 1;
  string status = 2;
  int64 created_at_unix = 3;
}

message GetOrderRequest {
  string order_id = 1;
}

message Order {
  string order_id = 1;
  string user_id = 2;
  int64 amount_cents = 3;
  string status = 4;
}
```

