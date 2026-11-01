import { evaluate, Truth } from '../common/RuleEngine';
@Entry @Component struct Index {
  @State mode: string = '本机使用'; @State result: Truth = 'UNKNOWN';
  build() { Column({ space: 16 }) {
    Text('知事 RuleFlow').fontSize(28).fontColor('#176B4D'); Text('看懂复杂通知，知道自己该怎么办。').fontSize(16);
    Text('当前：' + this.mode + ' · 共享规则结果：' + this.result);
    Button('验证本地三值规则').onClick(() => { this.result=evaluate({op:'eq',field:'profile.role',value:'student'}, {role:'student'}); });
    Button('导入通知').onClick(() => { this.mode='导入草稿待确认（需配置 Want/文件选择器）'; });
  }.padding(24).width('100%') }
}
