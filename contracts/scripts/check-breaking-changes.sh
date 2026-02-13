#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
SPEC_PATH="${REPO_ROOT}/docs/architecture/specs/platform-api.openapi.yaml"
BASE_SPEC_PATH="/tmp/platform-api.base.openapi.yaml"

if [[ ! -f "${SPEC_PATH}" ]]; then
  echo "OpenAPI spec not found at ${SPEC_PATH}" >&2
  exit 1
fi

if [[ "${GITHUB_EVENT_NAME:-}" != "pull_request" ]]; then
  echo "Skipping breaking-change check outside pull_request context."
  exit 0
fi

if [[ -z "${GITHUB_BASE_REF:-}" ]]; then
  echo "GITHUB_BASE_REF is required for breaking-change check." >&2
  exit 1
fi

git -C "${REPO_ROOT}" fetch origin "${GITHUB_BASE_REF}" --depth=1
git -C "${REPO_ROOT}" show "origin/${GITHUB_BASE_REF}:docs/architecture/specs/platform-api.openapi.yaml" > "${BASE_SPEC_PATH}"

ruby - "${BASE_SPEC_PATH}" "${SPEC_PATH}" <<'RUBY'
require 'set'
require 'yaml'

base_path = ARGV[0]
current_path = ARGV[1]

HTTP_METHODS = %w[get put post delete patch options head trace].freeze

def deref(doc, schema)
  return schema unless schema.is_a?(Hash)
  return schema unless schema.key?('$ref')

  ref = schema['$ref']
  return schema unless ref.start_with?('#/')

  ref.split('/').drop(1).reduce(doc) { |acc, key| acc[key] }
end

def schema_label(schema)
  return '{}' unless schema.is_a?(Hash)
  return schema['$ref'] if schema['$ref']
  schema['type'] || 'object'
end

def compare_schemas(base_doc, current_doc, base_schema, current_schema, location, errors)
  base_schema = deref(base_doc, base_schema)
  current_schema = deref(current_doc, current_schema)

  return if base_schema.nil? || current_schema.nil?
  unless current_schema.is_a?(Hash)
    errors << "#{location}: schema became non-object."
    return
  end

  if base_schema['type'] && current_schema['type'] && base_schema['type'] != current_schema['type']
    errors << "#{location}: type changed from #{base_schema['type']} to #{current_schema['type']}."
  end

  if base_schema['enum'].is_a?(Array)
    current_enum = current_schema['enum'].is_a?(Array) ? current_schema['enum'] : []
    removed = base_schema['enum'] - current_enum
    unless removed.empty?
      errors << "#{location}: enum values removed: #{removed.join(', ')}."
    end
  end

  base_required = Set.new(base_schema.fetch('required', []))
  current_required = Set.new(current_schema.fetch('required', []))
  newly_required = current_required - base_required

  base_props = base_schema.fetch('properties', {})
  current_props = current_schema.fetch('properties', {})
  unless base_props.is_a?(Hash) && current_props.is_a?(Hash)
    errors << "#{location}: properties shape changed from #{schema_label(base_schema)} to #{schema_label(current_schema)}."
    return
  end

  newly_required.each do |name|
    next unless base_props.key?(name)
    errors << "#{location}.#{name}: field changed from optional to required."
  end

  base_props.each do |name, prop_schema|
    unless current_props.key?(name)
      errors << "#{location}.#{name}: field removed."
      next
    end

    compare_schemas(
      base_doc,
      current_doc,
      prop_schema,
      current_props[name],
      "#{location}.#{name}",
      errors
    )
  end

  if base_schema['items']
    unless current_schema['items']
      errors << "#{location}: array items schema removed."
    else
      compare_schemas(
        base_doc,
        current_doc,
        base_schema['items'],
        current_schema['items'],
        "#{location}[]",
        errors
      )
    end
  end
end

def effective_security(doc, operation)
  operation.key?('security') ? operation['security'] : doc['security']
end

base_doc = YAML.safe_load(File.read(base_path))
current_doc = YAML.safe_load(File.read(current_path))
errors = []

base_paths = base_doc.fetch('paths', {})
current_paths = current_doc.fetch('paths', {})

base_paths.each do |path, path_item|
  unless current_paths.key?(path)
    errors << "Path removed: #{path}"
    next
  end

  HTTP_METHODS.each do |method|
    next unless path_item.is_a?(Hash) && path_item.key?(method)
    unless current_paths[path].is_a?(Hash) && current_paths[path].key?(method)
      errors << "Operation removed: #{method.upcase} #{path}"
      next
    end

    base_operation = path_item[method]
    current_operation = current_paths[path][method]

    if effective_security(base_doc, base_operation) != effective_security(current_doc, current_operation)
      errors << "Security requirements changed: #{method.upcase} #{path}"
    end

    base_params = Array(base_operation['parameters']).map { |p| p.is_a?(Hash) ? (p['name'] ? "#{p['in']}:#{p['name']}" : p['$ref']) : p }.compact.to_set
    current_params = Array(current_operation['parameters']).map { |p| p.is_a?(Hash) ? (p['name'] ? "#{p['in']}:#{p['name']}" : p['$ref']) : p }.compact.to_set
    removed_params = base_params - current_params
    removed_params.each { |param| errors << "Parameter removed for #{method.upcase} #{path}: #{param}" }

    base_request = base_operation['requestBody']
    current_request = current_operation['requestBody']
    if base_request && !current_request
      errors << "Request body removed: #{method.upcase} #{path}"
    elsif base_request && current_request
      if base_request['required'] == false && current_request['required'] == true
        errors << "Request body changed from optional to required: #{method.upcase} #{path}"
      end

      base_schema = base_request.dig('content', 'application/json', 'schema')
      current_schema = current_request.dig('content', 'application/json', 'schema')
      if base_schema && current_schema
        compare_schemas(
          base_doc,
          current_doc,
          base_schema,
          current_schema,
          "#{method.upcase} #{path} requestBody",
          errors
        )
      elsif base_schema && !current_schema
        errors << "JSON request schema removed: #{method.upcase} #{path}"
      end
    end

    base_responses = base_operation.fetch('responses', {})
    current_responses = current_operation.fetch('responses', {})
    base_responses.each do |status, response|
      unless current_responses.key?(status)
        errors << "Response removed for #{method.upcase} #{path}: #{status}"
        next
      end

      base_schema = response.dig('content', 'application/json', 'schema')
      current_schema = current_responses[status].dig('content', 'application/json', 'schema')
      if base_schema && current_schema
        compare_schemas(
          base_doc,
          current_doc,
          base_schema,
          current_schema,
          "#{method.upcase} #{path} response #{status}",
          errors
        )
      elsif base_schema && !current_schema
        errors << "JSON response schema removed for #{method.upcase} #{path}: #{status}"
      end
    end
  end
end

base_components = base_doc.dig('components', 'schemas') || {}
current_components = current_doc.dig('components', 'schemas') || {}
base_components.each do |name, schema|
  unless current_components.key?(name)
    errors << "Schema removed: components.schemas.#{name}"
    next
  end

  compare_schemas(
    base_doc,
    current_doc,
    schema,
    current_components[name],
    "components.schemas.#{name}",
    errors
  )
end

if errors.empty?
  puts "No incompatible OpenAPI changes detected."
else
  warn "Detected incompatible OpenAPI changes:"
  errors.uniq.each { |error| warn "- #{error}" }
  exit 1
end
RUBY
