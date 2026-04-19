#!/usr/bin/env ruby
# frozen_string_literal: true

require 'yaml'

path = ARGV[0] || 'backend/openapi.yaml'
unless File.exist?(path)
  warn "file not found: #{path}"
  exit 1
end

begin
  data = YAML.safe_load(File.read(path), permitted_classes: [], aliases: true)
rescue Psych::SyntaxError => e
  warn "yaml syntax error: #{e.message}"
  exit 1
end

unless data.is_a?(Hash)
  warn 'openapi file must be a top-level mapping'
  exit 1
end

%w[openapi paths].each do |required|
  unless data.key?(required)
    warn "openapi file missing required key: #{required}"
    exit 1
  end
end

puts 'ok'
