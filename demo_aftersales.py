"""Run a reproducible business demo without API keys or third-party packages."""
import json
from aftersales.service import AfterSalesService


def main():
    service = AfterSalesService()
    cases = {
        "物流查询": service.get_order("DEMO1003"),
        "补问商品状态": service.evaluate("DEMO1001", "no_reason_return"),
        "第七天可以申请": service.evaluate("DEMO1005", "no_reason_return", "intact"),
        "第八天转人工": service.evaluate("DEMO1006", "no_reason_return", "intact"),
        "质量故障转人工": service.evaluate("DEMO1002", "quality_issue"),
        "创建模拟退货工单": service.create_ticket("DEMO1001", "no_reason_return", "不喜欢，申请退货", "intact"),
    }
    print(json.dumps(cases, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
