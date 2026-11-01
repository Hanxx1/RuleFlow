import {describe,it,expect} from 'vitest';
import {matchLocal} from './localMatching';
import {emptyWorkspace,formAssertions} from './clientWorkspace';
const resources={rules:[{id:'r',label:'排名',ast:{op:'lte',field:'profile.rank_percent',value:20},evidence_ids:['block:notice']}],evidence:[{id:'block:notice',text:'排名前20%'}]};
describe('local matching',()=>{
 it('explains TRUE/FALSE with both sources',()=>{const w=emptyWorkspace('a');w.assertions=formAssertions({rank_percent:10});expect(matchLocal(resources,w,'c').relevance).toBe('TRUE');expect(matchLocal(resources,w,'c').rows[0].profileEvidence).toHaveLength(1);w.assertions=formAssertions({rank_percent:25});expect(matchLocal(resources,w,'c').relevance).toBe('FALSE')});
 it('never treats unconfirmed, expired, conflicted or unsupported facts as approval',()=>{const w=emptyWorkspace('a');expect(matchLocal(resources,w,'c').relevance).toBe('UNKNOWN');w.assertions=formAssertions({rank_percent:10});expect(matchLocal({...resources,evaluation:{unsupported_conditions:[{}]}},w,'c').relevance).toBe('UNKNOWN');w.assertions[0].confirmed=false;expect(matchLocal(resources,w,'c').relevance).toBe('UNKNOWN')});
 it('requires rule evidence and rejects executable AST',()=>{const w=emptyWorkspace('a');w.assertions=formAssertions({rank_percent:10});expect(matchLocal({...resources,evidence:[]},w,'c').relevance).toBe('UNKNOWN');expect(matchLocal({...resources,rules:[{...resources.rules[0],ast:{op:'eval',code:'anything'}}]},w,'c').relevance).toBe('UNKNOWN')});
});
