// Run against a local Vite dev server. Uses an isolated browser profile and synthetic courses.
const assert=require('node:assert/strict');
const path=require('node:path');
const {mkdir}=require('node:fs/promises');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const base=process.env.COURSE_TEST_BASE||'http://127.0.0.1:5186';
assert.equal(new URL(base).hostname,'127.0.0.1');
const output=path.resolve(process.argv[2]||'.runtime/course-draft-browser');

async function run(){
  await mkdir(output,{recursive:true});
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try{
    const page=await browser.newPage({viewport:{width:390,height:844}});
    const errors=[];page.on('pageerror',error=>errors.push(error.message));
    let decision=false,dialogs=0;
    page.on('dialog',async dialog=>{dialogs++;if(decision)await dialog.accept();else await dialog.dismiss()});
    const button=name=>page.getByRole('button',{name,exact:true});
    const dirtyRefresh=()=>page.evaluate(()=>{
      const event=new Event('beforeunload',{cancelable:true});window.dispatchEvent(event);return event.defaultPrevented;
    });
    await page.goto(base+'/courses');
    await button('新增课程').waitFor();
    await button('新增课程').click();
    assert.equal(await dirtyRefresh(),false);
    await page.getByLabel('课程名称',{exact:true}).fill('合成课程');
    await page.getByLabel('学期',{exact:true}).fill('2026 秋季');
    await button('取消编辑').click();
    await page.getByLabel('课程名称',{exact:true}).waitFor();
    assert.equal(await page.getByLabel('课程名称',{exact:true}).inputValue(),'合成课程');
    await button('保存课程').click();
    await page.getByRole('heading',{name:'合成课程',exact:true}).waitFor();
    assert.equal(await dirtyRefresh(),false);
    await button('课程要求').click();
    await button('编辑要求').first().click();
    await page.getByLabel('记录状态',{exact:true}).selectOption('待核对');
    await page.getByLabel('要求内容',{exact:true}).fill('用户记录：每周提交练习');
    await page.getByLabel('来源或用户声明',{exact:true}).fill('用户声明：合成课堂笔记');
    assert.equal(await dirtyRefresh(),true);
    const before=dialogs;
    await button('课程要求').click();assert.equal(dialogs,before); // Same tab keeps the editor.
    await button('资料').click();
    assert.equal(await page.getByLabel('要求内容',{exact:true}).inputValue(),'用户记录：每周提交练习');
    await button('编辑要求').first().click(); // Another requirement cannot silently replace the draft.
    assert.equal(await page.getByLabel('要求内容',{exact:true}).inputValue(),'用户记录：每周提交练习');
    await button('返回课程列表').click();
    assert.equal(await page.getByLabel('要求内容',{exact:true}).inputValue(),'用户记录：每周提交练习');
    await page.getByRole('link',{name:'← 返回工作台',exact:true}).click();
    assert.equal(new URL(page.url()).pathname,'/courses');
    // A real IndexedDB revision conflict leaves the input editable after a failed save.
    await page.evaluate(async()=>{
      const workspace=await import('/src/services/clientWorkspace.ts');
      const current=await workspace.loadWorkspace('offline');
      await workspace.saveWorkspace({...current,supplement:'另一页面的合成修改'});
    });
    await button('保留修改').click();
    await page.getByRole('alert').waitFor();
    assert.equal(await page.getByLabel('要求内容',{exact:true}).inputValue(),'用户记录：每周提交练习');
    await button('读取最新记录，保留草稿').click();
    await page.getByText('已读取最新记录，本次输入仍保留；请核对后再保存。',{exact:true}).waitFor();
    assert.equal(await dirtyRefresh(),true);
    await page.getByPlaceholder('例如：课堂展示',{exact:true}).fill('未添加字段');
    await button('保留修改').click();
    await page.getByText('要求及旧值历史已一同保存在本机。',{exact:true}).waitFor();
    assert.equal(await dirtyRefresh(),true); // Saving a requirement does not save a custom-field draft.
    await button('总览').click();
    assert.equal(await page.getByPlaceholder('例如：课堂展示',{exact:true}).inputValue(),'未添加字段');
    decision=true;await button('总览').click();decision=false;
    assert.equal(await dirtyRefresh(),false);
    await page.reload();await page.getByRole('heading',{name:'合成课程',exact:true}).waitFor();
    await page.getByRole('button').filter({has:page.getByRole('heading',{name:'合成课程',exact:true})}).click();
    await button('课程要求').click();
    await page.getByText('用户记录：每周提交练习',{exact:true}).waitFor();
    await button('编辑要求').first().click();
    await page.getByLabel('要求内容',{exact:true}).fill('待放弃的输入');
    decision=true;await button('资料').click();decision=false;
    await button('课程要求').click();
    await page.getByText('用户记录：每周提交练习',{exact:true}).waitFor();
    assert.equal(await page.getByLabel('要求内容',{exact:true}).count(),0);
    await button('编辑要求').first().click();
    await page.getByLabel('要求内容',{exact:true}).fill('切换账户前未保存输入');
    await page.evaluate(async()=>{
      const {useAccountStore}=await import('/src/stores/account.ts');
      useAccountStore().user={id:'synthetic-course-owner',email:'course@example.invalid'};
    });
    await button('新增课程').waitFor();assert.equal(await dirtyRefresh(),false);
    assert.equal(await page.getByText('切换账户前未保存输入',{exact:true}).count(),0);
    await page.setViewportSize({width:1280,height:900});
    await page.screenshot({path:path.join(output,'courses-desktop.png'),fullPage:true});
    // The standalone sample also protects edits, without writing account data.
    await page.goto(base+'/course-preview.html');
    await page.locator('.course-card').first().click();await button('课程要求').click();
    await button('编辑要求').first().click();await page.getByLabel('要求内容',{exact:true}).fill('样例未保存输入');
    await button('总览').click();
    assert.equal(await page.getByLabel('要求内容',{exact:true}).inputValue(),'样例未保存输入');
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    await page.screenshot({path:path.join(output,'courses-mobile.png'),fullPage:true});
    assert.deepEqual(errors,[]);assert.ok(dialogs>=8);
    console.log('PASS course drafts: switching, cancel, route leave, refresh guard, IndexedDB conflict/retry, saved reload, custom draft, identity reset, sample and narrow screen');
  }finally{await browser.close()}
}
run().catch(error=>{console.error(error);process.exitCode=1});
