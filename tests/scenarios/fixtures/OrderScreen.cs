using System;
using System.Data;

namespace Example
{
    public partial class OrderScreen
    {
        private void btnOpen_Click(object sender, EventArgs e)
        {
            int[] handles = gvwOrders.GetSelectedRows();
            if (handles.Length == 0)
                return;

            DataRow row = gvwOrders.GetDataRow(handles[0]);
            OpenOrder(row["DOCNUM"].ToString());
        }

        private void OpenOrder(string documentNumber)
        {
            // Existing framework dispatch; keep this method.
            ShowOrder(documentNumber);
        }
    }
}
