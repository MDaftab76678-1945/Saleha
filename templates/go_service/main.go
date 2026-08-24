package main

import (
	"encoding/json"
	"log"
	"net/http"
)

type HealthResponse struct {
	Status  string `json:"status"`
	Service string `json:"service"`
	Version string `json:"version"`
}

func healthHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(HealthResponse{
		Status:  "healthy",
		Service: "go-microservice",
		Version: "1.0.0",
	})
}

func rootHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{
		"message": "Welcome to Saleha Go Microservice",
	})
}

func main() {
	http.HandleFunc("/health", healthHandler)
	http.HandleFunc("/", rootHandler)
	log.Println("Go Server listening on :8080")
	log.Fatal(http.ListenAndServe(":8080", nil))
}

