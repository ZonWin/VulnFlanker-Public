package main

import "testing"

func TestBuildGrabbersSupportsWatchVulnSources(t *testing.T) {
	grabbers, err := buildGrabbers("avd,chaitin,oscs,ti,nox,threatbook,seebug,struts2,structs2,kev,venustech")
	if err != nil {
		t.Fatalf("buildGrabbers returned error: %v", err)
	}
	if got, want := len(grabbers), 11; got != want {
		t.Fatalf("grabber count = %d, want %d", got, want)
	}
}

func TestBuildGrabbersRejectsUnsupportedSource(t *testing.T) {
	_, err := buildGrabbers("avd,unknown")
	if err == nil {
		t.Fatal("buildGrabbers accepted unsupported source")
	}
}
