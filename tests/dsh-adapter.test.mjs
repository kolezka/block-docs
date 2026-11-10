import assert from 'node:assert/strict'
import test from 'node:test'
import plugin from '../dsh/index.js'

test('registers the skill and both agent briefs with their content', async () => {
  const providers = []
  const context = {
    skills: { registerProvider: create => providers.push(create()) },
    commands: { register: () => assert.fail('unexpected command') },
    systemPrompt: { section: () => assert.fail('unexpected prompt section') },
    inject: (_services, callback) => callback(context),
    on: () => assert.fail('unexpected hook'),
    logger: { warn: message => assert.fail(message) },
  }

  assert.equal(plugin.name, 'claude-compat-block-docs')
  plugin.apply(context, {})
  assert.equal(providers.length, 1)
  const provider = providers[0]
  const candidates = await provider.list({})
  assert.deepEqual(candidates.map(candidate => candidate.name).sort(), [
    'block-docs',
    'block-docs-agent-block-docs-verifier',
    'block-docs-agent-block-docs-writer',
  ])
  const contents = Object.fromEntries(await Promise.all(candidates.map(async candidate => {
    const definition = await provider.get(candidate, {})
    assert.equal(definition.name, candidate.name)
    return [candidate.name, definition.content]
  })))
  assert.match(contents['block-docs'], /# Block Documentation/)
  assert.match(contents['block-docs-agent-block-docs-verifier'], /## Verdicts and classes/)
  assert.match(contents['block-docs-agent-block-docs-writer'], /## Required brief/)
})
