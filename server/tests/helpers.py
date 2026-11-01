"""Shared API helpers; the client is bound to one isolated test lifespan."""
class ClientProxy:
    target = None

    def __getattr__(self, name):
        if self.target is None:
            raise RuntimeError('API client is only available inside an isolated test')
        return getattr(self.target, name)

client = ClientProxy()

def account(email):
 r=client.post('/api/v1/auth/register',json={'email':email,'password':'correct horse battery staple'}).json()['data']
 assert client.post('/api/v1/auth/verify',json={'token':r['development_verification_token']}).status_code==200
 return client.post('/api/v1/auth/login',json={'email':email,'password':'correct horse battery staple'}).json()['data']
def head(a): return {'Authorization':'Bearer '+a['access_token']}
def confirm_import(a,case_id):
 review=client.get('/api/v1/cases/'+case_id+'/reviews',headers=head(a)).json()['data']
 response=client.post('/api/v1/cases/'+case_id+'/confirm',headers=head(a),json={'revision':review['revision'],'action_ids':[item['id'] for item in review['candidate']['actions']],'no_deadline':True,'consent':True})
 assert response.status_code==200,response.text
